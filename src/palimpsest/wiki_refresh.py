"""Resume source-page regeneration from exact retained Knowledge change impacts.

The existing page compiler owns full-I generation and independent validation.
This coordinator only selects current affected pages and journals the separate
file-publication and PostgreSQL-import checkpoints. It never calls a provider.
"""

from copy import deepcopy
from contextlib import nullcontext
from pathlib import Path

from .canonical_store import PostgresRepository, connection
from .data import request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import _json
from . import knowledge_provenance
from .paper_wiki_runtime import PaperWikiRuntime
from .wiki_database import WikiDatabase
from .wiki_archive import build_archive
from .wiki_projection_store import ProjectionStore


PROFILE = 'wiki-change-refresh-v1'


def _fail(code, status=6):
    raise PalimpsestError(code, 'Wiki 변경 영향의 정확한 현재 페이지·검증·저장 상태를 확인하세요.', status)


def change_snapshot(row, description):
    """Label actual receipts; a source expansion is never a fabricated impact."""
    if row.get('impacts') is not None:
        if row['disposition'] != 'accepted_revision':
            _fail('wiki_refresh_change_receipt_missing')
        kind, impact = 'material_revision', deepcopy(row['impacts'])
    elif row.get('current_support_receipt') is not None and row['disposition'] in (
            'accepted_new', 'accepted_revision', 'reused'):
        kind, impact = 'current_support', None
    elif row['disposition'] == 'accepted_new' and row.get('outbox_present') is True:
        kind, impact = 'new_node', None
    else:
        _fail('wiki_refresh_change_receipt_missing')
    if not row.get('result_node_id') or not row.get('result_node_revision_id'):
        _fail('wiki_refresh_change_receipt_missing')
    support = row.get('current_support_receipt')
    if support is not None and (support['record_id'] != row['record_id']
                                or support['node_revision_id'] != row['result_node_revision_id']):
        _fail('wiki_refresh_change_receipt_missing')
    if impact is None:
        impact = {'source_revision_id': row['result_node_revision_id'], 'derivations': [], 'edges': [],
                  'edge_applicability': [], 'wiki_links': [], 'wiki_available': True}
    source_refs = description['direct_groundings'] + description.get('direct_data_groundings', [])
    source_refs += (description.get('current_transitive_source_refs', description['transitive_source_refs'])
                   + description.get('current_transitive_data_refs', description.get('transitive_data_refs', [])))
    return {'record_id': row['record_id'], 'change_kind': kind,
        'stored_impact_present': row.get('impacts') is not None,
        'source_revision_id': impact['source_revision_id'], 'result_knode_id': row['result_node_id'],
        'result_revision_id': row['result_node_revision_id'],
        'source_data_ids': sorted({ref['data_id'] for ref in source_refs}),
        'current_support_receipt': deepcopy(row.get('current_support_receipt')),
        'impact_projection': impact}


def select_targets(impact, wiki_id, import_id, catalog, snapshots, *, source_data_ids=()):
    """Resolve every current impacted source page; preserve historical-only refs."""
    selected = {entry['snapshot_id']: (owner, entry) for owner, entry in catalog['papers'].items()}
    grouped, historical = {}, []
    for link in impact['wiki_links']:
        if link['wiki_id'] != wiki_id:
            continue
        if link['request_id'] != import_id or link['snapshot_id'] not in selected:
            historical.append(deepcopy(link))
            continue
        owner, entry = selected[link['snapshot_id']]
        page = snapshots.get(entry['snapshot_id'])
        if (page is None or digest(page) != entry['snapshot_sha256']
                or page['kind'] != 'paper' or page['data_id'] != owner
                or page['page_id'] != entry['page_id']
                or link['node_revision_id'] != impact['source_revision_id']
                or link['item_key'] not in {item['item_key'] for item in page['items']}):
            _fail('wiki_refresh_impact_changed')
        if owner not in grouped:
            grouped[owner] = {'data_id': owner, 'page_id': page['page_id'],
                'snapshot_id': page['snapshot_id'], 'snapshot_sha256': entry['snapshot_sha256'],
                'source_execution_id': page['source_execution_id'],
                'metadata': deepcopy(page['metadata']), 'feedback_request_id': page['origin_request_id'],
                'impact_links': []}
        grouped[owner]['impact_links'].append(deepcopy(link))
    for owner in sorted(set(source_data_ids)):
        entry = catalog['papers'].get(owner)
        if entry is None or owner in grouped:
            continue
        page = snapshots.get(entry['snapshot_id'])
        if (page is None or digest(page) != entry['snapshot_sha256'] or page['kind'] != 'paper'
                or page['data_id'] != owner or page['page_id'] != entry['page_id']):
            _fail('wiki_refresh_impact_changed')
        grouped[owner] = {'data_id': owner, 'page_id': page['page_id'],
            'snapshot_id': page['snapshot_id'], 'snapshot_sha256': entry['snapshot_sha256'],
            'source_execution_id': page['source_execution_id'],
            'metadata': deepcopy(page['metadata']), 'feedback_request_id': page['origin_request_id'],
            'impact_links': []}
    for target in grouped.values():
        target['impact_links'].sort(key=lambda value: value['link_id'])
    return {'targets': [grouped[key] for key in sorted(grouped)],
            'historical_only_links': sorted(historical, key=lambda value: value['link_id'])}


class WikiRefreshRuntime:
    def __init__(self, dsn, artifact_root, directory):
        self.dsn, self.artifact_root = dsn, Path(artifact_root)
        self.store = ProjectionStore(Path(directory))
        self.database = WikiDatabase(dsn, artifact_root)
        self.repository = PostgresRepository(dsn)

    def _path(self, identifier, name):
        return f'refreshes/{request_id(identifier)}/{name}'

    def _plan(self, identifier):
        value = self.store.read_json(self._path(identifier, 'plan.json'))
        if value is None:
            _fail('wiki_refresh_not_found', 2)
        if (value.get('schema_version') != PROFILE or value.get('refresh_id') != identifier
                or value.get('plan_sha256') != digest({key: item for key, item in value.items()
                                                     if key != 'plan_sha256'})):
            _fail('wiki_refresh_plan_changed')
        return value

    def _runtime(self, identifier):
        return PaperWikiRuntime(self.dsn, self.artifact_root,
                                self.store.root / self._path(identifier, 'wiki'))

    def prepare(self, impact_record_ids, wiki_id, identifier, *, source_data_ids=None):
        from .data import data_id
        if isinstance(impact_record_ids, str):
            impact_record_ids = [impact_record_ids]
        if not isinstance(impact_record_ids, list) or not impact_record_ids:
            _fail('invalid_wiki_refresh_impacts', 2)
        impact_record_ids = sorted({request_id(value) for value in impact_record_ids})
        if source_data_ids is not None and not isinstance(source_data_ids, list):
            _fail('invalid_wiki_refresh_sources', 2)
        source_data_ids = sorted({data_id(value) for value in (source_data_ids or [])})
        wiki_id, identifier = map(request_id, (wiki_id, identifier))
        requested = {'impact_record_ids': impact_record_ids, 'wiki_id': wiki_id,
                     'source_data_ids': source_data_ids}
        with self.store.locked():
            if self.store.read_json(self._path(identifier, 'plan.json')) is not None:
                prior = self._plan(identifier)
                if any(prior[key] != value for key, value in requested.items()):
                    _fail('idempotency_conflict')
                return {**prior, 'replayed': True}
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            self.database._ready(conn)
            rows = conn.execute('''SELECT r.record_id,r.result_node_id,r.result_node_revision_id,r.disposition,
                i.source_revision_id,i.impacts,to_jsonb(s) AS current_support_receipt,
                EXISTS(SELECT 1 FROM compiler_runtime.k_outbox o WHERE o.record_id=r.record_id) AS outbox_present
                FROM compiler_runtime.k_compilation_records r
                LEFT JOIN compiler_runtime.k_revision_impacts i USING(record_id)
                LEFT JOIN canonical_store.knowledge_current_supports s USING(record_id)
                WHERE r.record_id=ANY(%s::uuid[]) AND r.result_node_id IS NOT NULL
                    AND r.disposition IN ('accepted_new','accepted_revision','reused')
                ORDER BY r.record_id''', (impact_record_ids,)).fetchall()
            if len(rows) != len(impact_record_ids):
                _fail('wiki_refresh_impact_not_found', 2)
            impacts = _json(rows)
            provenance = knowledge_provenance.load(conn)
            changes = [change_snapshot(impact, knowledge_provenance.describe(provenance,
                       impact['result_node_revision_id'])) for impact in impacts]
            verified_sources = {owner for change in changes for owner in change['source_data_ids']}
            if not set(source_data_ids) <= verified_sources:
                _fail('wiki_refresh_unrelated_source', 2)
            selected = self.database._import(conn, wiki_id)
            catalog = conn.execute('''SELECT payload FROM wiki_projection.catalogs
                WHERE wiki_id=%s AND catalog_sha256=%s''', (wiki_id, selected['catalog_sha256'])).fetchone()['payload']
            snapshots = {str(row['snapshot_id']): row['payload'] for row in conn.execute('''SELECT snapshot_id,payload
                FROM wiki_projection.snapshots WHERE wiki_id=%s AND snapshot_id=ANY(%s::uuid[])''',
                (wiki_id, [entry['snapshot_id'] for entry in catalog['papers'].values()])).fetchall()}
            grouped, historical = {}, {}
            for change in changes:
                targets = select_targets(change['impact_projection'], wiki_id, selected['request_id'], catalog, snapshots,
                                         source_data_ids=source_data_ids)
                for target in targets['targets']:
                    if target['data_id'] not in grouped:
                        grouped[target['data_id']] = target
                    else:
                        grouped[target['data_id']]['impact_links'].extend(target['impact_links'])
                historical.update({link['link_id']: link for link in targets['historical_only_links']})
            for target in grouped.values():
                target['impact_links'] = sorted({link['link_id']: link for link in target['impact_links']}.values(),
                                                key=lambda link: link['link_id'])
            current_revisions = _json(conn.execute('''SELECT knode_id,current_revision_id
                FROM canonical_store.knowledge_nodes WHERE knode_id=ANY(%s::uuid[]) ORDER BY knode_id''',
                (list({change['result_knode_id'] for change in changes}),)).fetchall())
            if any(not any(change['result_knode_id'] == node['knode_id']
                           and change['result_revision_id'] == node['current_revision_id'] for change in changes)
                   for node in current_revisions):
                _fail('wiki_refresh_revision_changed')
            for node in current_revisions:
                node['current_support_signature'] = knowledge_provenance.describe(provenance,
                    node['current_revision_id']).get('current_support_signature')
            version_heads = self._version_heads(conn, list(grouped))
        plan = {'schema_version': PROFILE, 'refresh_id': identifier, **requested,
            'base_import_id': selected['request_id'],
            'base_catalog_sha256': selected['catalog_sha256'],
            'changes': changes, 'targets': [grouped[key] for key in sorted(grouped)],
            'current_revisions': current_revisions, 'source_version_heads': version_heads,
            'historical_only_links': [historical[key] for key in sorted(historical)],
            'sync_request_id': self.repository.allocate_id(),
            'canonical_writes': 0, 'new_d2i_calls': 0, 'provider_calls': 0}
        for target in plan['targets']:
            target['request_id'] = self.repository.allocate_id()
        plan['plan_sha256'] = digest(plan)
        with self.store.locked():
            if self.store.read_json(self._path(identifier, 'plan.json')) is not None:
                prior = self._plan(identifier)
                if any(prior[key] != value for key, value in requested.items()):
                    _fail('idempotency_conflict')
                return {**prior, 'replayed': True}
            self.store.write_json(self._path(identifier, 'plan.json'), plan)
        return {**plan, 'replayed': False}

    @staticmethod
    def _version_heads(conn, owners):
        return _json(conn.execute('''SELECT s.series_id,s.head_version_id FROM canonical_store.data_series s
            WHERE EXISTS(SELECT 1 FROM canonical_store.data_versions v
                WHERE v.series_id=s.series_id AND v.data_id=ANY(%s::text[])) ORDER BY s.series_id''',
            (owners,)).fetchall())

    def _bindings(self, conn, plan):
        nodes = _json(conn.execute('''SELECT knode_id,current_revision_id FROM canonical_store.knowledge_nodes
            WHERE knode_id=ANY(%s::uuid[]) ORDER BY knode_id''',
            ([node['knode_id'] for node in plan['current_revisions']],)).fetchall())
        provenance = knowledge_provenance.load(conn)
        for node in nodes:
            node['current_support_signature'] = knowledge_provenance.describe(provenance,
                node['current_revision_id']).get('current_support_signature')
        if nodes != plan['current_revisions']:
            _fail('wiki_refresh_revision_changed')
        if self._version_heads(conn, [target['data_id'] for target in plan['targets']]) != plan['source_version_heads']:
            _fail('wiki_refresh_source_version_changed')

    def _current(self, plan):
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            head = self.database._head(conn, plan['wiki_id'])
            self._bindings(conn, plan)
        if head not in (plan['base_import_id'], plan['sync_request_id']):
            _fail('wiki_refresh_head_changed')

    def _publish(self, plan, runtime, *, transaction_guard=None):
        # Keep K and already-known Data-series heads fixed through the existing
        # short atomic Wiki import, on that same connection. No model call or
        # nested connection waits while holding the publication fence.
        def guard(conn):
            conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR SHARE')
            if transaction_guard:
                transaction_guard(conn)
            conn.execute('''SELECT series_id FROM canonical_store.data_series
                WHERE series_id=ANY(%s::uuid[]) ORDER BY series_id FOR SHARE''',
                ([head['series_id'] for head in plan['source_version_heads']],))
            self._bindings(conn, plan)
        return self.database.sync(plan['wiki_id'], plan['sync_request_id'], runtime.store.root,
                                  expected_head=plan['base_import_id'], transaction_guard=guard)

    def _state(self, identifier):
        return self.store.read_json(self._path(identifier, 'state.json'), default={'restored': False})

    def _save(self, identifier, state):
        self.store.replace_json(self._path(identifier, 'state.json'), state)

    def _committed(self, plan, state):
        if 'sync_manifest_sha256' not in state:
            return None
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            row = conn.execute('''SELECT expected_head,manifest_sha256,result FROM wiki_projection.imports
                WHERE wiki_id=%s AND request_id=%s''', (plan['wiki_id'], plan['sync_request_id'])).fetchone()
        if row is None:
            return None
        if str(row['expected_head']) != plan['base_import_id'] or row['manifest_sha256'] != state['sync_manifest_sha256']:
            _fail('wiki_refresh_import_changed')
        return _json(row['result'])

    @staticmethod
    def _completion_result(plan, state, imported):
        results = state.get('page_results')
        if (not isinstance(results, list) or len(results) != len(plan['targets'])
                or any(result.get('paper_page_id') != target['page_id'] for result, target in zip(results, plan['targets']))):
            _fail('wiki_refresh_completion_changed')
        return {'refresh_id': plan['refresh_id'], 'state': 'completed',
            'effect': 'validated_source_pages_refreshed',
            'regenerated_pages': len(results), 'page_results': results,
            'import': imported, 'historical_only_links': len(plan['historical_only_links']),
            'canonical_writes': 0, 'new_d2i_calls': 0}

    @staticmethod
    def _empty_result(plan):
        return {'refresh_id': plan['refresh_id'], 'state': 'completed',
            'effect': 'no_current_page_effect', 'regenerated_pages': 0,
            'historical_only_links': len(plan['historical_only_links']),
            'canonical_writes': 0, 'new_d2i_calls': 0, 'provider_calls': 0}

    def _finish(self, plan, state, imported):
        result = self._completion_result(plan, state, imported)
        state['result'] = result
        self._save(plan['refresh_id'], state)
        return result

    def _advance(self, identifier, *, retry_failed=False, publication_guard=None, transaction_guard=None):
        plan, state = self._plan(identifier), self._state(identifier)
        if state.get('result') is not None:
            if plan['targets']:
                imported = self._committed(plan, state)
                if imported is None:
                    _fail('wiki_refresh_completion_missing')
                expected = self._completion_result(plan, state, imported)
            else:
                expected = self._empty_result(plan)
            cached, compared = deepcopy(state['result']), deepcopy(expected)
            if plan['targets']:
                # WikiDatabase adds this transport flag to a returned reply;
                # the immutable imports.result row deliberately omits it.
                for result in (cached, compared):
                    receipt = result.get('import')
                    if (not isinstance(receipt, dict) or ('replayed' in receipt
                            and type(receipt['replayed']) is not bool)):
                        _fail('wiki_refresh_completion_changed')
                    receipt.pop('replayed', None)
            if cached != compared:
                _fail('wiki_refresh_completion_changed')
            return deepcopy(state['result'])
        committed = self._committed(plan, state)
        if committed is not None:
            return self._finish(plan, state, committed)
        self._current(plan)
        if not plan['targets']:
            result = self._empty_result(plan)
            state['result'] = result
            self._save(identifier, state)
            return result
        if not state['restored']:
            self.database.restore(plan['wiki_id'], self.store.root / self._path(identifier, 'wiki'),
                                  import_id=plan['base_import_id'])
            state['restored'] = True
            self._save(identifier, state)
        runtime, results = self._runtime(identifier), []
        for target in plan['targets']:
            attempts = state.get('attempts', {}).get(target['request_id'], [])
            attempt = attempts[-1] if attempts else target
            request = attempt['request_id']
            refs = '; '.join(f"Record {change['record_id']}: {change['source_revision_id']} -> {change['result_revision_id']}"
                             for change in plan['changes'])
            notes = ['Recheck this complete retained source page after Knowledge revision changes. '
                f"{refs}. These identifiers identify review context, "
                'not evidence or authority. Preserve source-only claims and report unresolved source issues. '
                'Do not import inferred K conclusions, reparse D2I, fetch D as replacement evidence, or create I.']
            notes.extend(attempt.get('review_notes', []))
            job = runtime.prepare(target['source_execution_id'], request, target['metadata'],
                feedback_request_id=attempt['feedback_request_id'], review_notes=notes)
            generator = runtime.store.read_json(f'jobs/{request}/generator-exchange.json')
            if generator is None and attempt.get('reuse_generator_from'):
                prior = runtime.show(attempt['reuse_generator_from'])
                if prior['input_snapshot'] != job['input_snapshot'] or prior['profile'] != job['profile']:
                    _fail('wiki_refresh_retry_input_changed')
                generator = runtime.store.read_json(f"jobs/{prior['request_id']}/generator-exchange.json")
                if generator is None:
                    _fail('wiki_refresh_retry_generator_missing')
                runtime.model_request(request, 'generator')
            if job['state'] in ('prepared', 'failed') and generator is not None:
                with publication_guard() if publication_guard else nullcontext():
                    runtime.stage(request, generator)
                job = runtime.show(request)
            validator = runtime.store.read_json(f'jobs/{request}/validator-exchange.json')
            if job['state'] == 'proposed' and validator is not None:
                with publication_guard() if publication_guard else nullcontext():
                    runtime.decide(request, validator)
                job = runtime.show(request)
            retryable_generator = (job['state'] == 'failed' and generator is None
                and job.get('failure', {}).get('phase') == 'generator'
                and 'response' not in job.get('failure', {}))
            retryable_validator = (job['state'] == 'proposed' and validator is None
                and job.get('failure', {}).get('phase') == 'validator'
                and 'response' not in job.get('failure', {}))
            if retry_failed and (retryable_generator or retryable_validator):
                next_attempt = {'request_id': self.repository.allocate_id(),
                    'feedback_request_id': request if retryable_generator else job['feedback_request_id'],
                    'retry_of_request_id': request,
                    'review_notes': deepcopy(attempt.get('review_notes', [])),
                    'reason': 'retry_retained_' + ('generator' if retryable_generator else 'validator') + '_transport_failure'}
                if retryable_validator:
                    next_attempt['reuse_generator_from'] = request
                state.setdefault('attempts', {}).setdefault(target['request_id'], []).append(next_attempt)
                self._save(identifier, state)
                return self._advance(identifier, publication_guard=publication_guard, transaction_guard=transaction_guard)
            if job['state'] in ('needs_review', 'failed') or retryable_validator:
                return {'refresh_id': identifier, 'state': 'failed' if retryable_validator else job['state'], 'request_id': request,
                    'page_id': target['page_id'], 'job': job, 'published_to_database': False}
            if job['state'] in ('prepared', 'proposed'):
                phase = 'generator' if job['state'] == 'prepared' else 'validator'
                return {'refresh_id': identifier,
                    'phase': phase, 'page_id': target['page_id'],
                    **runtime.model_request(request, phase),
                    'state': 'awaiting_' + phase, 'published_to_database': False}
            if job['state'] != 'compiled':
                _fail('wiki_refresh_job_state')
            results.append(deepcopy(job['result']))
        self._current(plan)
        state.update(page_results=results, sync_manifest_sha256=build_archive(runtime.store)['manifest_sha256'])
        self._save(identifier, state)
        imported = self._publish(plan, runtime, transaction_guard=transaction_guard)
        return self._finish(plan, state, imported)

    def advance(self, identifier, *, retry_failed=False, publication_guard=None, transaction_guard=None):
        """Perform local checkpoints until a model exchange or review is required."""
        identifier = request_id(identifier)
        with self.store.locked():
            if type(retry_failed) is not bool:
                _fail('invalid_wiki_refresh_retry', 2)
            return self._advance(identifier, retry_failed=retry_failed,
                publication_guard=publication_guard, transaction_guard=transaction_guard)

    def accept(self, identifier, phase, exchange, *, checkpoint=None,
               publication_guard=None, transaction_guard=None):
        """Retain an actual exchange; delegate source/independence/publication checks."""
        identifier = request_id(identifier)
        with self.store.locked():
            if phase not in ('generator', 'validator'):
                _fail('wiki_refresh_exchange_state')
            plan = self._plan(identifier)
            state = self._state(identifier)
            runtime = self._runtime(identifier)
            identifiers = [target['request_id'] for target in plan['targets']] + [
                attempt['request_id'] for attempts in state.get('attempts', {}).values() for attempt in attempts]
            if any(runtime.store.read_json(f'jobs/{request}/{phase}-exchange.json') == exchange
                   for request in identifiers):
                return self._advance(identifier, publication_guard=publication_guard, transaction_guard=transaction_guard)
            current = self._advance(identifier, publication_guard=publication_guard, transaction_guard=transaction_guard)
            if current['state'] != 'awaiting_' + phase:
                _fail('wiki_refresh_exchange_state')
            with publication_guard() if publication_guard else nullcontext():
                if phase == 'generator':
                    runtime.stage(current['request_id'], exchange)
                else:
                    runtime.decide(current['request_id'], exchange, checkpoint=checkpoint)
            return self._advance(identifier, publication_guard=publication_guard, transaction_guard=transaction_guard)

    def call_failed(self, identifier, phase, failure, *, publication_guard=None, transaction_guard=None):
        identifier = request_id(identifier)
        if isinstance(failure, dict) and set(failure) == {'failure'}:
            failure = failure['failure']
        with self.store.locked():
            current = self._advance(identifier, publication_guard=publication_guard, transaction_guard=transaction_guard)
            if current['state'] != 'awaiting_' + phase:
                _fail('wiki_refresh_exchange_state')
            result = self._runtime(identifier).call_failed(current['request_id'], phase, failure)
            return {'refresh_id': identifier, 'state': 'failed', 'failure': result,
                    'request_id': current['request_id'], 'published_to_database': False}

    def retry_review(self, identifier, reason):
        """Schedule an operator-requested semantic review; never clear a hold automatically."""
        identifier = request_id(identifier)
        if not isinstance(reason, str) or not reason.strip() or '\x00' in reason:
            _fail('wiki_refresh_review_reason_required', 2)
        try:
            reason.encode('utf-8')
        except UnicodeError:
            _fail('wiki_refresh_review_reason_required', 2)
        with self.store.locked():
            plan, state = self._plan(identifier), self._state(identifier)
            if state.get('result') is not None:
                _fail('wiki_refresh_no_held_review')
            self._current(plan)
            runtime = self._runtime(identifier)
            for target in plan['targets']:
                attempts = state.get('attempts', {}).get(target['request_id'], [])
                prior_attempt = attempts[-1] if attempts else target
                prior = runtime.store.read_json(f"jobs/{prior_attempt['request_id']}/job.json")
                if prior is None:
                    _fail('wiki_refresh_no_held_review')
                prior = runtime.show(prior_attempt['request_id'])
                if prior['state'] == 'compiled':
                    continue
                semantic_failure = (prior['state'] == 'failed' and 'response' in prior.get('failure', {}))
                if prior['state'] != 'needs_review' and not semantic_failure:
                    _fail('wiki_refresh_no_held_review')
                runtime._check_profile(prior)
                attempt = {'request_id': self.repository.allocate_id(),
                    'feedback_request_id': prior['request_id'], 'retry_of_request_id': prior['request_id'],
                    'reason': 'operator_requested_semantic_review',
                    'review_notes': [*prior_attempt.get('review_notes', []), reason.strip()]}
                state.setdefault('attempts', {}).setdefault(target['request_id'], []).append(attempt)
                self._save(identifier, state)
                return {'refresh_id': identifier, 'state': 'review_requested',
                    'request_id': attempt['request_id'], 'previous_request_id': prior['request_id'],
                    'reason': reason.strip(), 'published_to_database': False,
                    'canonical_writes': 0, 'new_d2i_calls': 0, 'provider_calls': 0}
            _fail('wiki_refresh_no_held_review')

    def show(self, identifier):
        identifier = request_id(identifier)
        with self.store.locked():
            return {'plan': self._plan(identifier), 'progress': self._state(identifier)}
