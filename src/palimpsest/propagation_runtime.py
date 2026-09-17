"""Execute a scoped causal worklist through existing Knowledge and Wiki services.

Only this coordinator selects work. It never reparses a source, manufactures I,
or calls a provider inside a database transaction.
"""
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import json

from psycopg.types.json import Jsonb

from .canonical_store import connection
from .data import data_id, request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import KnowledgeRuntime, MODEL, _json
from .knowledge_revision_runtime import enumerate_impacts, MATERIALITY_POLICY
from .propagation_queue import PropagationQueue, _uuid
from .wiki_projection_store import ProjectionStore
from .wiki_refresh import WikiRefreshRuntime
from . import k2k, knowledge_provenance as provenance, revalidation
from . import k2k_effective, k2k_effective_runtime as effective_runtime
from . import propagation_anomalies as anomalies
from .knowledge_requests import edge_generation_request, edge_validation_request
from .data_versions import immutable_versions


PROFILE = 'causal-source-pairs-v1'
DEPENDENCY_ERRORS = {'k2k_premise_needs_revalidation','revalidation_dependency_pending',
    'revalidation_premises_changed','knowledge_input_changed','knowledge_state_changed','n2e_endpoint_needs_revalidation',
    'k2k_edge_premise_pending'}
FRESHNESS_ERRORS = {'knowledge_state_changed','knowledge_input_changed','knowledge_revision_target_changed',
    'revalidation_target_changed','revalidation_premises_changed','revalidation_endpoints_changed',
    'n2e_review_target_changed','n2e_review_endpoints_changed','n2e_comparison_base_changed'}
FRESHNESS_ERRORS.update({'k2k_edge_revision_changed','revalidation_effective_premises_changed','k2k_edge_premise_pending'})


def _fail(code, status=6):
    raise PalimpsestError(code,'전파 범위·정확한 Knowledge 입력·Wiki 검증 상태를 확인하세요.',status)


def _ids(values, validator=request_id):
    if not isinstance(values,(list,tuple)) or not values:
        _fail('propagation_scope_required',2)
    checked=[validator(value) for value in values]
    if len(checked)!=len(set(checked)):
        _fail('duplicate_propagation_scope',2)
    return sorted(checked)


def _signature(node):
    return {key:node.get(key) for key in ('knode_id','knode_revision_id','content_fingerprint','current_support_signature')}


class PropagationRuntime:
    def __init__(self,dsn,artifact_root,directory,*,realm_guard=None,require_realm=False,model_profile=None):
        self.dsn=dsn
        self.artifact_root=Path(artifact_root)
        self.directory=Path(directory)
        self.queue=PropagationQueue(dsn)
        self.knowledge=KnowledgeRuntime(dsn)
        self.store=ProjectionStore(self.directory)
        self.wiki=WikiRefreshRuntime(dsn,self.artifact_root,self.directory/'wiki-refresh')
        self.model=deepcopy(MODEL if model_profile is None else model_profile)
        if type(require_realm) is not bool or (realm_guard is not None and realm_guard.source_dsn != dsn):
            _fail('realm_configuration_mismatch',3)
        self.realm_guard,self.require_realm=realm_guard,require_realm

    def prepare(self,identifier,root_record_ids,*,allowed_data_ids=None,wiki_ids=None,
                data_version_ids=None,data_version_mode='current',discovery=True):
        roots=_ids(root_record_ids)
        if type(discovery) is not bool or data_version_mode not in ('current','pinned'):
            _fail('invalid_propagation_policy',2)
        with connection(self.dsn) as conn,conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            prior_run=conn.execute('SELECT * FROM compiler_runtime.propagation_runs WHERE run_id=%s',
                (request_id(identifier),)).fetchone()
            if prior_run is not None:
                from .realm_automation import replay_scope
                scope,policy=replay_scope(prior_run,roots=roots,allowed_data_ids=allowed_data_ids,wiki_ids=wiki_ids,
                    version_ids=data_version_ids,version_mode=data_version_mode,discovery=discovery,guard=self.realm_guard)
                return self._prepared(identifier,scope,policy)
            if self.require_realm and self.realm_guard is None:
                raise PalimpsestError('realm_configuration_required', '자동 전파의 Realm catalog와 저장소 설정이 필요합니다.',3)
            rows=_json(conn.execute('SELECT * FROM compiler_runtime.k_compilation_records WHERE record_id=ANY(%s::uuid[]) ORDER BY record_id',(roots,)).fetchall())
            if len(rows)!=len(roots) or any(r['disposition'] not in ('accepted_new','accepted_revision','reused','no_material_delta') for r in rows):
                _fail('propagation_root_not_accepted',2)
            owners=set()
            for row in rows:
                refs=[row['result_node_revision_id']] if row['result_node_revision_id'] else []
                if row['result_edge_revision_id']:
                    edge=conn.execute('SELECT from_knode_revision_id,to_knode_revision_id FROM canonical_store.knowledge_edge_revisions WHERE kedge_revision_id=%s',(row['result_edge_revision_id'],)).fetchone()
                    refs.extend(str(v) for v in edge.values())
                for ref in refs:
                    owners.update(r['data_id'] for r in conn.execute('SELECT canonical_store.derivation_source_data(%s) AS data_id',(ref,)).fetchall())
            realm_scope=(self.realm_guard.prepare(conn,roots,allowed_data_ids=allowed_data_ids,
                version_ids=data_version_ids,version_mode=data_version_mode) if self.realm_guard else None)
            allowed=(realm_scope['allowed_data_ids'] if realm_scope else _ids(allowed_data_ids or sorted(owners),data_id))
            registered=conn.execute('SELECT data_id,byte_size,media_type FROM canonical_store.data WHERE data_id=ANY(%s::text[]) ORDER BY data_id',(allowed,)).fetchall()
            if len(registered)!=len(allowed) or not owners&set(allowed):
                _fail('propagation_source_scope_mismatch',2)
            catalogs=_json(conn.execute('''SELECT w.wiki_id,w.current_import_id,c.payload FROM wiki_projection.wikis w
                JOIN wiki_projection.imports i ON i.request_id=w.current_import_id
                JOIN wiki_projection.catalogs c ON c.wiki_id=w.wiki_id AND c.catalog_sha256=i.catalog_sha256
                ORDER BY w.wiki_id''').fetchall())
            selected=((_ids(wiki_ids) if wiki_ids else []) if wiki_ids is not None else
                      [r['wiki_id'] for r in catalogs if set(r['payload']['papers'])&set(allowed)])
            wiki_imports={r['wiki_id']:r['current_import_id'] for r in catalogs if r['wiki_id'] in selected}
            if len(wiki_imports)!=len(selected):
                _fail('propagation_wiki_not_found',2)
            realm_versions=[version['version_id'] for version in realm_scope['series_versions']] if realm_scope else []
            if data_version_ids:
                versions=immutable_versions(conn,sorted(set(_ids(data_version_ids))|set(realm_versions)))
            else:
                heads=conn.execute('''SELECT v.version_id FROM canonical_store.data_series s
                    JOIN canonical_store.data_versions v ON v.version_id=s.head_version_id
                    WHERE v.data_id=ANY(%s::text[]) ORDER BY v.version_id''',(allowed,)).fetchall()
                version_ids=sorted({str(r['version_id']) for r in heads}|set(realm_versions))
                versions=immutable_versions(conn,version_ids) if version_ids else []
            if any(v['data_id'] not in allowed for v in versions):
                _fail('propagation_version_scope_mismatch',2)
            effective_enabled = effective_runtime.available(conn)
        scope={'root_record_ids':roots,'allowed_data_ids':allowed,'wiki_ids':selected,'wiki_imports':wiki_imports,
            'data_versions':versions,'data_version_mode':data_version_mode,'source_manifest':_json(registered),
            'wiki_metadata_permission':'selected_wiki_topic_key_title_scope; full I only for allowed sources'}
        if realm_scope is not None:
            scope['realm_scope']=realm_scope
        policy={'schema_version':PROFILE,'model':deepcopy(self.model),'discovery':discovery,
            'discovery_context':'two_distinct_current_K_in_selected_source_scope',
            'mandatory_dependencies':'all_exact_active_consumers','d2i_allowed':False,'d2k_allowed':False,
            'semantic_completion_cap':None,'wiki_claim_basis':'complete_retained_I_source_only',
            'anomaly_detection':anomalies.PROFILE,'repeated_outcome':'observe',
            'materiality_policy':MATERIALITY_POLICY}
        if effective_enabled:
            policy['effective_k2k'] = k2k_effective.PROFILE
        return self._prepared(identifier,scope,policy)

    def _prepared(self,identifier,scope,policy):
        result=self.queue.prepare(identifier,scope,policy)
        with self.store.locked():
            path=f'runs/{identifier}/manifest.json'
            old=self.store.read_json(path)
            manifest={'run_id':identifier,'request_fingerprint':result['request_fingerprint'],'scope':scope,'policy':policy}
            if old is not None and old!=manifest:
                _fail('propagation_manifest_changed')
            if old is None: self.store.write_json(path,manifest)
        return {**result,'manifest_file':str(self.directory/path),'actual_delivery':False}

    def _task(self,task_id):
        with connection(self.dsn) as conn:
            row=conn.execute('SELECT * FROM compiler_runtime.propagation_tasks WHERE task_id=%s',(request_id(task_id),)).fetchone()
        if row is None: _fail('propagation_task_not_found',2)
        return _json(row)

    def _nodes(self,conn,run,*,usable=True):
        nodes=self.knowledge._nodes(conn)
        allowed=run['scope']['allowed_data_ids']
        result=[]
        for node in nodes:
            checks=conn.execute('''SELECT canonical_store.k_revision_supported_by_version_data(%s,%s::text[]) AS scoped,
                compiler_runtime.current_k2k_premise(%s) AS usable''',(node['knode_revision_id'],allowed,node['knode_revision_id'])).fetchone()
            if checks['scoped'] and (not usable or checks['usable']): result.append(node)
        return result

    @staticmethod
    def _owner(conn,refs,allowed):
        owners=set()
        for ref in refs:
            owners.update(r['data_id'] for r in conn.execute('SELECT canonical_store.derivation_source_data(%s) AS data_id',(ref,)).fetchall())
        eligible=sorted(owners&set(allowed))
        if not eligible: _fail('propagation_source_scope_mismatch')
        return eligible[0]

    @staticmethod
    def _versions(run,nodes):
        owners={d for n in nodes for d in n.get('source_data_ids',n.get('grounding_data_ids',[]))}
        versions=[v['version_id'] for v in run['scope'].get('data_versions',[]) if v['data_id'] in owners]
        if not versions:
            if any(n.get('data_version_supports') for n in nodes): _fail('propagation_version_binding_required')
            return {}
        return {'data_version_ids':versions,'data_version_mode':run['scope']['data_version_mode']}

    def _expanded(self,conn,task,run):
        row=_json(conn.execute('SELECT * FROM compiler_runtime.k_compilation_records WHERE record_id=%s',(task['payload']['record_id'],)).fetchone())
        nodes=self.knowledge._nodes(conn);by_node={n['knode_id']:n for n in nodes}
        state=provenance.load(conn)
        edges=self.knowledge._edges(conn);by_edge={e['kedge_id']:e for e in edges}
        saved=conn.execute('SELECT impacts FROM compiler_runtime.k_revision_impacts WHERE record_id=%s',(row['record_id'],)).fetchone()
        support=conn.execute('SELECT * FROM canonical_store.knowledge_current_supports WHERE record_id=%s',(row['record_id'],)).fetchone()
        impacts=[saved['impacts']] if saved and task['kind']=='outbox' else []
        if support is not None: impacts.append(enumerate_impacts(conn,row['result_node_revision_id']))
        made=[];coverage=[]
        snapshot=conn.execute('SELECT input_snapshot FROM compiler_runtime.k_execution_contexts WHERE execution_id=%s',(row['execution_id'],)).fetchone()['input_snapshot']
        before_nodes={n['knode_id']:n['knode_revision_id'] for n in snapshot.get('existing_nodes',[])}
        for impact in impacts:
            targets=[];prior_pairs=[]
            for dep in impact['derivations']:
                target=next((n for n in nodes if n['knode_revision_id']==dep['result_node_revision_id']),None)
                if target is None or provenance.support_record(state,target['knode_revision_id'])!=dep['record_id']:
                    continue
                premise_ids=state['by_record'][dep['record_id']]['premise_revision_ids']
                premises=[by_node[state['revisions'][ref]['knode_id']] for ref in premise_ids]
                payload={'target_knode_id':target['knode_id'],'enumerated_revision_id':target['knode_revision_id'],
                    'input_signature':digest([_signature(p) for p in premises])}
                required_edges = effective_runtime.required_edge_state(conn, self.knowledge, dep['record_id'])
                if required_edges:
                    payload['input_signature'] = digest({'nodes': [_signature(p) for p in premises], 'edges': required_edges})
                child=self.queue.enqueue(conn,run['run_id'],'node_revalidate',payload,
                    cause_record_id=row['record_id'],parent_task_id=task['task_id'])
                made.append(child['task_id']);targets.append(target['knode_revision_id'])
            edge_ids={r['kedge_id'] for r in impact['edges']+impact['edge_applicability']}
            for edge_id in sorted(edge_ids):
                edge=by_edge.get(edge_id)
                if edge is None: continue
                pair=[by_node[edge[k]] for k in ('from_knode_id','to_knode_id')]
                old_pair=[before_nodes.get(edge[k],edge[r]) for k,r in (
                    ('from_knode_id','from_knode_revision_id'),('to_knode_id','to_knode_revision_id'))]
                observed_pair=list(old_pair)
                original=[edge['from_knode_revision_id'],edge['to_knode_revision_id']]
                confirmed=conn.execute('''SELECT 1 FROM canonical_store.knowledge_edge_applicability_events
                    WHERE semantic_kedge_revision_id=%s AND from_knode_revision_id=%s AND to_knode_revision_id=%s''',
                    (edge['kedge_revision_id'],*old_pair)).fetchone()
                if old_pair!=original and confirmed is None:
                    # Concurrent parent changes may leave an intermediate pair
                    # unevaluated. Compare against the actual original pair's
                    # latest explicit judgment, never invent an intermediate one.
                    old_pair=original
                prior_pairs.append({'kedge_revision_id':edge['kedge_revision_id'],'observed_pair':observed_pair,
                    'comparison_pair':old_pair,'intermediate_unreviewed':observed_pair!=old_pair})
                payload={'target_kedge_id':edge_id,'enumerated_revision_id':edge['kedge_revision_id'],
                    'prior_pair':old_pair,'input_signature':digest([_signature(n) for n in pair])}
                child=self.queue.enqueue(conn,run['run_id'],'edge_revalidate',payload,
                    cause_record_id=row['record_id'],parent_task_id=task['task_id'])
                made.append(child['task_id'])
            coverage.append({'source_revision_id':impact['source_revision_id'],'enumerated':impact,
                'current_node_targets':targets,'current_edge_targets':sorted(edge_ids),'prior_applicability_pairs':prior_pairs})
        edge_consumers = []
        if row['result_edge_id']:
            for dep in effective_runtime.consumers(conn, row['result_edge_id']):
                dep = _json(dep)
                target = by_node[dep['knode_id']]
                route = state['by_record'][dep['record_id']]
                premises = [by_node[state['revisions'][ref]['knode_id']] for ref in route['premise_revision_ids']]
                current_edges = effective_runtime.required_edge_state(conn, self.knowledge, dep['record_id'])
                payload = {'target_knode_id': target['knode_id'], 'enumerated_revision_id': target['knode_revision_id'],
                    'input_signature': digest({'nodes': [_signature(p) for p in premises], 'edges': current_edges})}
                child = self.queue.enqueue(conn, run['run_id'], 'node_revalidate', payload,
                    cause_record_id=row['record_id'], parent_task_id=task['task_id'])
                made.append(child['task_id'])
                edge_consumers.append({**dep, 'current_edges': current_edges, 'task_id': child['task_id']})
        semantic_change=row['disposition'] in ('accepted_new','accepted_revision')
        assessment=conn.execute('SELECT validation FROM compiler_runtime.k_revalidation_decisions WHERE record_id=%s',
            (row['record_id'],)).fetchone() if row['result_edge_revision_id'] else None
        applicability_change=bool(assessment and assessment['validation'].get('confirmed') is True
            and assessment['validation'].get('material_change') is True)
        from . import n2e_runtime
        if row['result_edge_revision_id'] and n2e_runtime.available(conn):
            modern_assessment=conn.execute('SELECT material_change FROM compiler_runtime.n2e_review_decisions WHERE record_id=%s',
                (row['record_id'],)).fetchone()
            applicability_change=applicability_change or bool(modern_assessment and modern_assessment['material_change'])
        material=task['kind']=='outbox' and (semantic_change or applicability_change)
        if material and run['policy']['discovery']:
            eligible=self._nodes(conn,run)
            anchors=[]
            if row['result_node_id'] in by_node: anchors=[by_node[row['result_node_id']]]
            elif row['result_edge_id'] in by_edge:
                edge=by_edge[row['result_edge_id']]
                anchors=[by_node[edge[k]] for k in ('from_knode_id','to_knode_id')]
            pairs={}
            if row['result_edge_id']:
                if len(anchors)==2: pairs[tuple(sorted(n['knode_id'] for n in anchors))]=anchors
            else:
                for anchor in anchors:
                    for other in eligible:
                        if anchor['knode_id']!=other['knode_id']:
                            pair=sorted([anchor,other],key=lambda n:n['knode_id'])
                            pairs[tuple(n['knode_id'] for n in pair)]=pair
            kind=task['payload']['operation']
            for pair in pairs.values():
                if kind=='n2e' and all(n['kind']=='observation' for n in pair) and not n2e_runtime.available(conn): continue
                payload={'node_ids':[n['knode_id'] for n in pair],
                    'input_signature':digest([_signature(n) for n in pair])}
                if kind == 'k2k' and run['policy'].get('effective_k2k') == k2k_effective.PROFILE:
                    edge_state = effective_runtime.stable_edges(conn, self.knowledge, payload['node_ids'])
                    payload['effective_edge_ids'] = [value['kedge_id'] for value in edge_state]
                    payload['input_signature'] = digest({'nodes': [_signature(n) for n in pair], 'edges': edge_state})
                child=self.queue.enqueue(conn,run['run_id'],kind,payload,
                    cause_record_id=row['record_id'],parent_task_id=task['task_id'])
                made.append(child['task_id'])
        self.queue._event(conn,run['run_id'],'dependencies_enumerated',{'record_id':row['record_id'],
            'event_id':task['payload'].get('event_id'),'support_record_id':task['payload'].get('support_record_id'),
            'material':material,'maintenance':support is not None,
            'semantic_revision_change':semantic_change,'applicability_change':applicability_change,
            'effective_edge_consumers':edge_consumers,
            'coverage':coverage,'child_task_ids':sorted(set(made))},task['task_id'])
        self.queue.finish(conn,task,task['lease_token'],{'effect':'maintenance_dispatched' if task['kind']=='support_refresh' else 'outbox_dispatched',
            'event_id':task['payload'].get('event_id'),'support_record_id':task['payload'].get('support_record_id'),
            'record_id':row['record_id'],'child_task_ids':sorted(set(made)),'enumeration_complete':True})

    def _wiki_tasks(self,run_id):
        with connection(self.dsn) as conn,conn.transaction():
            self.queue._fence(conn);run=self.queue._run(conn,run_id,lock=True)
            if run['state']!='running': return
            self.queue.harvest(conn,run)
            remaining=conn.execute("SELECT 1 FROM compiler_runtime.propagation_tasks WHERE run_id=%s AND kind<>'wiki_refresh' AND state<>'done' LIMIT 1",(run_id,)).fetchone()
            if remaining: return
            records=_json(conn.execute('''SELECT DISTINCT r.record_id FROM compiler_runtime.k_compilation_records r
                WHERE r.result_node_revision_id IS NOT NULL AND
                (r.disposition IN ('accepted_new','accepted_revision') OR EXISTS(
                    SELECT 1 FROM canonical_store.knowledge_current_supports s WHERE s.record_id=r.record_id)) AND
                (%s::jsonb ? r.record_id::text OR EXISTS(SELECT 1 FROM compiler_runtime.propagation_execution_bindings b
                    JOIN compiler_runtime.propagation_tasks t USING(task_id) WHERE b.execution_id=r.execution_id AND t.run_id=%s)
                ) ORDER BY r.record_id''',(Jsonb(run['scope']['root_record_ids']),run_id)).fetchall())
            if not records: return
            refs=[r['record_id'] for r in records]
            for wiki_id in run['scope']['wiki_ids']:
                self.queue.enqueue(conn,run_id,'wiki_refresh',{'wiki_id':wiki_id,'impact_record_ids':refs},cause_record_id=refs[0])

    def _release_dependencies(self,run_id):
        run=self.queue.show(run_id)
        if run['state']!='running': return
        for task in run['tasks']:
            if task['state']=='blocked' and task['error_code'] in ('propagation_dependency_waiting','k2k_edge_premise_inapplicable'):
                with connection(self.dsn) as conn:
                    nodes={n['knode_id']:n for n in self.knowledge._nodes(conn)}
                    if task['kind']=='node_revalidate':
                        state=provenance.load(conn);node=nodes.get(task['payload']['target_knode_id'])
                        support=state['by_record'].get(provenance.support_record(state,node['knode_revision_id'])) if node else None
                        refs=([nodes[state['revisions'][r]['knode_id']]['knode_revision_id'] for r in support['premise_revision_ids']] if support else [])
                    elif task['kind']=='edge_revalidate':
                        edge=next((e for e in self.knowledge._edges(conn) if e['kedge_id']==task['payload']['target_kedge_id']),None)
                        refs=[nodes[edge[k]]['knode_revision_id'] for k in ('from_knode_id','to_knode_id')] if edge else []
                    elif task['kind'] in ('n2e','k2k'):
                        refs=([nodes[n]['knode_revision_id'] for n in task['payload']['node_ids']]
                            if all(n in nodes for n in task['payload']['node_ids']) else [])
                    else: refs=[]
                    ready=bool(refs) and all(conn.execute('SELECT compiler_runtime.current_k2k_premise(%s) AS ok',(r,)).fetchone()['ok'] for r in refs)
                    if ready and task['kind'] == 'node_revalidate' and support:
                        required_edges = effective_runtime.required_edge_state(conn, self.knowledge, support['record_id'])
                        ready = all(value['status'] == 'applicable' for value in required_edges)
                    if ready and task['kind'] == 'k2k' and task['payload'].get('effective_edge_ids'):
                        usable_edges = effective_runtime.stable_edges(conn, self.knowledge, task['payload']['node_ids'])
                        ready = set(task['payload']['effective_edge_ids']) <= {edge['kedge_id'] for edge in usable_edges}
                if ready: self.queue.retry(task['task_id'],'Exact prerequisite supports are now current; re-evaluate the retained obligation.',
                    actor_ref='dependency_worker')

    def _anomaly(self, conn, task, run):
        if task['kind']!='outbox' or run['policy'].get('anomaly_detection') is None:
            return None
        record=_json(conn.execute('SELECT * FROM compiler_runtime.k_compilation_records WHERE record_id=%s',
            (task['payload']['record_id'],)).fetchone())
        witness=anomalies.inspect_record(conn,run,record)
        if witness is None: return None
        action=run['policy'].get('repeated_outcome','halt')
        if action=='observe':
            prior=conn.execute('''SELECT 1 FROM compiler_runtime.propagation_events
                WHERE run_id=%s AND event_type='semantic_return_observed' AND payload->>'witness_sha256'=%s''',
                (run['run_id'],witness['witness_sha256'])).fetchone()
            if prior is None:
                self.queue._event(conn,run['run_id'],'semantic_return_observed',witness,task['task_id'])
            return None
        if action!='halt': _fail('unsupported_propagation_repetition_policy')
        acknowledged=conn.execute('''SELECT 1 FROM compiler_runtime.propagation_events
            WHERE run_id=%s AND event_type='semantic_anomaly_acknowledged' AND payload->>'witness_sha256'=%s''',
            (run['run_id'],witness['witness_sha256'])).fetchone()
        if acknowledged:
            anomalies.assert_fresh(conn,run,witness)
            return None
        self.queue.suspend_anomaly(conn,task,witness)
        return {'action':'needs_human','state':'needs_human','run_id':run['run_id'],'task_id':task['task_id'],
            'reason':'propagation_semantic_oscillation','witness_sha256':witness['witness_sha256']}

    def next(self,run_id,lease_seconds=180):
        self._release_dependencies(run_id)
        self._wiki_tasks(run_id)
        task=self.queue.claim(run_id,lease_seconds)
        if task is not None: return self.advance(task['task_id'],task['lease_token'])
        result=self.queue.settle(run_id)
        return {'action':result['status'],'state':result['status'],'run_id':run_id,'run':result}

    def _execution(self,conn,task):
        row=conn.execute('''SELECT c.execution_id FROM compiler_runtime.k_execution_contexts c
            JOIN compiler_runtime.propagation_execution_bindings b USING(execution_id)
            WHERE b.task_id=%s AND c.request_id=%s''',(task['task_id'],task['request_id'])).fetchone()
        return str(row['execution_id']) if row else None

    def _prepare_knowledge(self,task,run):
        with connection(self.dsn) as conn:
            nodes={n['knode_id']:n for n in self.knowledge._nodes(conn)}
            if task['kind']=='node_revalidate':
                target=nodes.get(task['payload']['target_knode_id'])
                if target is None: _fail('revalidation_target_changed')
                state=provenance.load(conn);support=state['by_record'].get(provenance.support_record(state,target['knode_revision_id']))
                if support is None: _fail('revalidation_source_review_required')
                chosen=[nodes[state['revisions'][r]['knode_id']] for r in support['premise_revision_ids']]
            elif task['kind']=='edge_revalidate':
                edge=next((e for e in self.knowledge._edges(conn) if e['kedge_id']==task['payload']['target_kedge_id']),None)
                if edge is None: _fail('revalidation_target_changed')
                chosen=[nodes[edge[k]] for k in ('from_knode_id','to_knode_id')]
                prior_pair=task['payload']['prior_pair']
                current_pair=[n['knode_revision_id'] for n in chosen]
                if conn.execute('''SELECT 1 FROM canonical_store.knowledge_edge_applicability_events
                        WHERE semantic_kedge_revision_id=%s AND from_knode_revision_id=%s AND to_knode_revision_id=%s''',
                        (edge['kedge_revision_id'],*current_pair)).fetchone():
                    prior_pair=current_pair
            else:
                chosen=[nodes[value] for value in task['payload']['node_ids']]
            refs=[n['knode_revision_id'] for n in chosen]
            if any(not conn.execute('SELECT compiler_runtime.current_k2k_premise(%s) AS ok',(ref,)).fetchone()['ok'] for ref in refs):
                _fail('revalidation_dependency_pending')
            owner=self._owner(conn,refs,run['scope']['allowed_data_ids'])
        options={**self._versions(run,chosen),'model_profile':deepcopy(run['policy']['model']),
            'propagation_claim':{'task_id':task['task_id'],'lease_token':task['lease_token']}}
        if task['kind']=='node_revalidate':
            return revalidation.prepare_node(self.knowledge,target['knode_revision_id'],task['request_id'],data_id=owner,**options)
        if task['kind']=='edge_revalidate':
            from . import n2e_runtime
            with connection(self.dsn) as conn:
                modern_n2e=n2e_runtime.available(conn)
            if modern_n2e:
                return n2e_runtime.prepare_review(self.knowledge,edge['kedge_revision_id'],task['request_id'],data_id=owner,
                    prior_pair=prior_pair,**options)
            return revalidation.prepare_edge(self.knowledge,edge['kedge_revision_id'],task['request_id'],data_id=owner,
                prior_pair=prior_pair,**options)
        edge_refs = None
        if task['kind'] == 'k2k' and task['payload'].get('effective_edge_ids'):
            with connection(self.dsn) as conn:
                actual_edges = {edge['kedge_id']: edge['kedge_revision_id'] for edge in self.knowledge._edges(conn)}
            edge_refs = [actual_edges[identifier] for identifier in task['payload']['effective_edge_ids']]
        packet=(self.knowledge.inference_input(owner,refs,edge_revision_ids=edge_refs) if task['kind']=='k2k' else {'schema_version':'n2e-input-v1','nodes':chosen})
        return self.knowledge.prepare(task['kind'],owner,task['request_id'],packet,**options)

    def _knowledge_request(self,job,task,phase):
        directory=self.directory/'calls'/task['task_id']/task['request_id']/str(task['attempt'])
        with connection(self.dsn) as conn:
            previous=conn.execute('''SELECT payload FROM compiler_runtime.propagation_events
                WHERE task_id=%s AND event_type='model_request_prepared'
                  AND payload->>'execution_id'=%s AND payload->>'phase'=%s ORDER BY created_at DESC,event_id DESC''',
                (task['task_id'],job['execution_id'],phase)).fetchall()
        for event in previous:
            candidate=Path(event['payload']['request_file'])
            try:
                candidate.resolve().relative_to(self.directory.resolve())
                request=json.loads(candidate.read_text(encoding='utf-8'))
                failed=candidate.parent/Path(request['output_file']).with_suffix('.failure.json')
                if not failed.exists():
                    directory=candidate.parent
                    break
            except (OSError,ValueError,KeyError):
                continue
        if job['input_snapshot']['input'].get('schema_version') == k2k_effective.INPUT_SCHEMA:
            exported = effective_runtime.prepare_call(self.knowledge, job['execution_id'], phase, directory)
            path = exported['request_file']
        elif job['input_snapshot'].get('edge_review_target'):
            from . import n2e_runtime
            exported=n2e_runtime.prepare_call(self.knowledge,job['execution_id'],phase,directory)
            path=exported['request_file']
        elif job['input_snapshot'].get('revalidation_target'):
            exported=revalidation.prepare_call(self.knowledge,job['execution_id'],phase,directory)
            path=exported['request_file']
        else:
            context=self.knowledge.validation_context(job['execution_id']) if phase=='validator' else None
            snapshot=job['input_snapshot']
            if job['operation']=='n2e':
                prompt,schema=edge_generation_request(snapshot) if phase=='generator' else edge_validation_request(context)
            elif phase=='generator':
                prompt,schema=k2k.generation_request(snapshot)
            else:
                prompt,schema=k2k.validation_request(context)
            value={'prompt':prompt,'schema':schema,'images':[],'input_sha256':job['input_digest'] if phase=='generator' else context['validation_context_sha'],
                'output_file':phase+'-response.json','delivered_knowledge_revision_ids':[n['knode_revision_id'] for n in snapshot['input']['nodes']]}
            if snapshot.get('data_versions'): value['delivered_data_version_ids']=[v['version_id'] for v in snapshot['data_versions']]
            store=ProjectionStore(directory)
            with store.locked():
                old=store.read_json(phase+'-request.json')
                if old is not None and old!=value: _fail('propagation_call_changed')
                if old is None: store.write_json(phase+'-request.json',value)
            path=str(directory/(phase+'-request.json'))
        with self.queue.transaction(task['task_id'],task['lease_token']) as (conn,current,run):
            self.queue._event(conn,run['run_id'],'model_request_prepared',{'execution_id':job['execution_id'],
                'phase':phase,'request_file':path,'attempt':current['attempt']},current['task_id'])
        return {'action':'model_request','operation':'knowledge','task_id':task['task_id'],'lease_token':task['lease_token'],
            'run_id':task['run_id'],'phase':phase,'request_file':path,'execution_id':job['execution_id'],'task_state':'leased'}

    @contextmanager
    def _publication(self,task_id,token):
        with self.queue.transaction(task_id,token): yield

    def _wiki_guard(self,task_id,token):
        def guard(conn):
            self.queue._assert(conn,task_id,token)
        return {'publication_guard':lambda:self._publication(task_id,token),'transaction_guard':guard}

    def _wiki_result(self,task,token,result):
        if result['state']=='completed':
            with self.queue.transaction(task['task_id'],token) as (conn,current,run):
                self.queue.finish(conn,current,token,{'effect':'wiki_refreshed','refresh_id':task['request_id'],'result':result})
            return {'action':'task_completed','task_id':task['task_id'],'task_state':'done','run_id':task['run_id']}
        if result['state'].startswith('awaiting_'):
            return {'action':'model_request','operation':'wiki','task_id':task['task_id'],'lease_token':token,
                'run_id':task['run_id'],'phase':result['phase'],'request_file':result['request_file'],'task_state':'leased'}
        self.queue.block(task['task_id'],token,'wiki_refresh_'+result['state'],result)
        return {'action':'blocked','task_id':task['task_id'],'run_id':task['run_id'],'reason':result['state']}

    def advance(self,task_id,token):
        try:
            with self.queue.transaction(task_id,token) as (conn,task,run):
                if task['kind'] in ('outbox','support_refresh'):
                    held=self._anomaly(conn,task,run)
                    if held is not None: return held
                    self._expanded(conn,task,run)
                    return {'action':'task_completed','task_id':task_id,'run_id':run['run_id'],'task_state':'done'}
                execution=self._execution(conn,task)
                if task['kind']=='node_revalidate' and execution is None:
                    node=conn.execute('SELECT current_revision_id FROM canonical_store.knowledge_nodes WHERE knode_id=%s',(task['payload']['target_knode_id'],)).fetchone()
                    ref=str(node['current_revision_id']) if node else None
                    checked=conn.execute('SELECT compiler_runtime.current_k2k_premise(%s) AS valid,canonical_store.current_k_support_record(%s) AS support',(ref,ref)).fetchone() if ref else None
                    if checked and checked['valid'] and checked['support']:
                        self.queue.finish(conn,task,token,{'effect':'covered_by_current_validated_support','node_revision_id':ref,'support_record_id':str(checked['support'])})
                        return {'action':'task_completed','task_id':task_id,'run_id':run['run_id'],'task_state':'done'}
            if task['kind']=='wiki_refresh':
                with connection(self.dsn) as conn:
                    sources=set()
                    for row in conn.execute('SELECT result_node_revision_id FROM compiler_runtime.k_compilation_records WHERE record_id=ANY(%s::uuid[])',
                            (task['payload']['impact_record_ids'],)).fetchall():
                        sources.update(item['data_id'] for item in conn.execute('SELECT canonical_store.derivation_source_data(%s) AS data_id',
                            (row['result_node_revision_id'],)).fetchall())
                selected=sorted(sources&set(run['scope']['allowed_data_ids']))
                prepared=self.wiki.prepare(task['payload']['impact_record_ids'],task['payload']['wiki_id'],task['request_id'],source_data_ids=selected)
                if any(t['data_id'] not in run['scope']['allowed_data_ids'] for t in prepared['targets']):
                    _fail('propagation_wiki_source_outside_scope')
                expected=run['scope']['wiki_imports'][task['payload']['wiki_id']]
                if prepared['base_import_id']!=expected:
                    _fail('propagation_wiki_import_changed')
                result=self.wiki.advance(task['request_id'],retry_failed=True,**self._wiki_guard(task_id,token))
                return self._wiki_result(task,token,result)
            job=self.knowledge.show(execution) if execution else self._prepare_knowledge(task,run)
            if execution:
                with self.queue.transaction(task_id,token) as (conn,current,run):
                    retry=conn.execute('''SELECT payload FROM compiler_runtime.propagation_events
                        WHERE task_id=%s AND event_type='retry_requested' AND payload->>'request_id'=%s
                        ORDER BY created_at DESC,event_id DESC LIMIT 1''',(task_id,current['request_id'])).fetchone()
                    retryable=retry and (job['state'] in ('failed','needs_human') or
                        retry['payload'].get('previous_error_code')=='knowledge_invalid_response')
                    if retryable: task=self.queue.rotate_request(conn,current,retry['payload']['reason'])
                if retryable: job=self._prepare_knowledge(task,run)
            if job['state'] in ('completed','zero_output'):
                with self.queue.transaction(task_id,token) as (conn,current,run):
                    self.queue.finish(conn,current,token,{'effect':'knowledge_evaluated','execution_id':job['execution_id'],
                        'execution_state':job['state'],'record_ids':[r['record_id'] for r in job['records']]})
                return {'action':'task_completed','task_id':task_id,'run_id':run['run_id'],'task_state':'done'}
            if job['state'] in ('failed','needs_human'):
                self.queue.block(task_id,token,'knowledge_'+job['state'],{'execution_id':job['execution_id']})
                return {'action':'blocked','task_id':task_id,'run_id':run['run_id'],'reason':job['state']}
            return self._knowledge_request(job,task,'generator' if job['state']=='prepared' else 'validator')
        except PalimpsestError as error:
            if error.code in ('propagation_claim_lost','propagation_claim_required'): raise
            code='propagation_dependency_waiting' if error.code in DEPENDENCY_ERRORS else error.code
            self.queue.block(task_id,token,code,{'error_code':error.code})
            return {'action':'blocked','task_id':task_id,'reason':code}

    def accept(self,task_id,token,phase,exchange):
        if phase not in ('generator','validator'): _fail('invalid_propagation_phase',2)
        task=self._task(task_id)
        if task['kind']=='wiki_refresh':
            result=self.wiki.accept(task['request_id'],phase,exchange,**self._wiki_guard(task_id,token))
            self.queue.transport_succeeded(task_id,token,phase)
            return self._wiki_result(task,token,result)
        with self.queue.transaction(task_id,token) as (conn,task,run):
            execution=self._execution(conn,task)
        if execution is None: _fail('propagation_execution_missing')
        try:
            function=self.knowledge.stage if phase=='generator' else self.knowledge.decide
            function(execution,exchange['response'],exchange['receipt'],propagation_claim={'task_id':task_id,'lease_token':token})
        except PalimpsestError as error:
            if error.code in FRESHNESS_ERRORS:
                with self.queue.transaction(task_id,token) as (conn,task,run):
                    conn.execute("UPDATE compiler_runtime.operation_executions SET state='failed',error_code=%s,updated_at=clock_timestamp() WHERE execution_id=%s",(error.code,execution))
                    self.knowledge._event(conn,self.knowledge._job(conn,execution),'failed',error.code)
                    self.queue.rotate_request(conn,task,error.code)
                self.queue.transport_succeeded(task_id,token,phase)
                return self.advance(task_id,token)
            if error.code=='propagation_claim_lost': raise
            if error.code == 'k2k_edge_premise_inapplicable':
                self.queue.block(task_id, token, error.code, {'execution_id': execution, 'phase': phase, 'error_code': error.code})
                return {'action': 'blocked', 'task_id': task_id, 'run_id': task['run_id'], 'reason': error.code}
            if error.code in ('data_version_head_changed','data_version_context_changed','propagation_input_outside_scope'):
                self.queue.block(task_id,token,error.code,{'execution_id':execution,'phase':phase,'error_code':error.code})
                return {'action':'blocked','task_id':task_id,'run_id':task['run_id'],'reason':error.code}
            try:
                self.knowledge.record_call_failure(execution,phase,exchange['receipt'],error.code,response=exchange['response'])
            except PalimpsestError:
                # Invalid transport metadata is not a delivered model receipt.
                # Preserve the rejection in the workflow journal instead.
                pass
            self.queue.block(task_id,token,'knowledge_invalid_response',{'execution_id':execution,'phase':phase,'error_code':error.code})
            return {'action':'blocked','task_id':task_id,'run_id':task['run_id'],'reason':error.code}
        self.queue.transport_succeeded(task_id,token,phase)
        return self.advance(task_id,token)

    def call_failed(self,task_id,token,phase,failure):
        task=self._task(task_id)
        if task['kind']=='wiki_refresh':
            self.wiki.call_failed(task['request_id'],phase,failure,**self._wiki_guard(task_id,token))
        else:
            with self.queue.transaction(task_id,token) as (conn,task,run): execution=self._execution(conn,task)
            self.knowledge.record_dispatch_failure(execution,phase,failure.get('failure',failure))
        details=failure.get('failure',failure)
        queued=self.queue.transport_retry(task_id,token,details.get('error_code','provider_failed'),{'phase':phase,'failure':details})
        return {'action':'blocked' if queued['state']=='blocked' else 'retry_wait',
            'task_id':task_id,'run_id':task['run_id'],'reason':queued['error_code']}

    def retry(self,task_id,reason,*,acknowledge_anomaly=None,actor_ref='local'):
        task=self._task(task_id)
        if task['error_code']=='propagation_semantic_oscillation':
            if acknowledge_anomaly is None:
                _fail('propagation_anomaly_acknowledgement_required')
            data_id(acknowledge_anomaly)
            def confirm(conn,run,current):
                found=conn.execute('''SELECT event_id,payload FROM compiler_runtime.propagation_events
                    WHERE run_id=%s AND event_type='semantic_anomaly' AND payload->>'record_id'=%s
                    ORDER BY created_at DESC,event_id DESC LIMIT 1''',
                    (run['run_id'],current['payload']['record_id'])).fetchone()
                if found is None or found['payload']['witness_sha256']!=acknowledge_anomaly:
                    _fail('propagation_anomaly_acknowledgement_changed')
                anomalies.assert_fresh(conn,run,found['payload'])
                self.queue._event(conn,run['run_id'],'semantic_anomaly_acknowledged',
                    {'witness_sha256':acknowledge_anomaly,'diagnostic_event_id':str(found['event_id']),
                     'record_id':current['payload']['record_id'],'actor_ref':actor_ref,'reason':reason},task_id)
            return self.queue.retry(task_id,reason,actor_ref=actor_ref,precondition=confirm)
        if acknowledge_anomaly is not None:
            _fail('unexpected_propagation_anomaly_acknowledgement')
        if task['error_code'] in ('propagation_wiki_import_changed','propagation_wiki_source_outside_scope',
                'propagation_source_scope_mismatch','propagation_version_scope_mismatch','data_version_head_changed',
                'data_version_context_changed','propagation_input_outside_scope','wiki_refresh_head_changed',
                'wiki_database_head_changed','wiki_refresh_revision_changed','wiki_refresh_source_version_changed',
                'wiki_implementation_changed','propagation_anomaly_scope_changed'):
            _fail('propagation_new_scope_required')
        if task['kind']=='wiki_refresh' and task['error_code'] in ('wiki_refresh_needs_review','wiki_refresh_failed'):
            self.wiki.retry_review(task['request_id'],reason)
        return self.queue.retry(task_id,reason,actor_ref=actor_ref)
