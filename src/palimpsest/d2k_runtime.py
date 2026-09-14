"""User-confirmed D2K preparation; never entered from I2K error handling."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import tempfile

from psycopg.types.json import Jsonb

from .artifact_store import ArtifactStore
from .canonical_store import PostgresRepository, connection
from .data import data_id as check_data_id, request_id
from .data_versions import immutable_versions
from .errors import PalimpsestError
from .i2k import digest
from . import d2k


MANIFEST = 'user-requested-d2k-v1'


def fail(code, status=6):
    raise PalimpsestError(code,'D2K의 사용자 요청·원본 범위·모델·정확한 확인 내용을 확인하세요.',status)


def available(conn):
    return conn.execute("SELECT to_regclass('compiler_runtime.d2k_preparations') IS NOT NULL AS ok").fetchone()['ok']


def load_authorization(conn, identifier, *, lock=False):
    request_id(identifier)
    if not available(conn):
        fail('d2k_schema_required',3)
    if lock:
        conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('d2k-grant:'+identifier,))
    row = conn.execute('''SELECT a.authorization_id,a.actor_ref,a.manifest_sha256,
        p.preparation_id,p.data_id,p.packet,p.manifest FROM compiler_runtime.d2k_authorizations a
        JOIN compiler_runtime.d2k_preparations p USING(preparation_id)
        WHERE authorization_id=%s''',(identifier,)).fetchone()
    if row is None:
        fail('d2k_user_confirmation_required',2)
    value = json.loads(json.dumps(row,default=str))
    if (value['manifest_sha256']!=digest(value['manifest']) or value['manifest']['input']!=value['packet']
            or value['manifest']['data_id']!=value['data_id'] or value['manifest']['schema_version']!=MANIFEST):
        fail('d2k_authorization_changed')
    d2k.check_input(value['packet'])
    return value


def bind_execution(conn, authorization_id, packet, model, versions, mode, nodes, prior_execution_id=None):
    """Bind an explicit request to its reviewed source and Knowledge catalog."""
    grant = load_authorization(conn, authorization_id, lock=True)
    manifest = grant['manifest']
    if (packet != grant['packet'] or model != manifest['model'] or versions != manifest['data_versions']
            or mode != manifest['data_version_mode']):
        fail('d2k_authorization_scope_mismatch')
    history = conn.execute('''SELECT e.execution_id,e.state FROM compiler_runtime.d2k_execution_authorizations a
        JOIN compiler_runtime.operation_executions e USING(execution_id)
        WHERE a.authorization_id=%s ORDER BY e.execution_id DESC''', (authorization_id,)).fetchall()
    if history:
        latest = history[0]
        if latest['state'] in ('prepared', 'proposed'):
            fail('d2k_request_in_progress')
        if (prior_execution_id is None or str(latest['execution_id']) != prior_execution_id
                or latest['state'] not in ('failed', 'needs_human')):
            fail('d2k_new_user_request_required')
    elif prior_execution_id is not None:
        fail('invalid_d2k_retry')
    approved = {n['knode_revision_id']: n for n in manifest['existing_knowledge']}
    current = {n['knode_revision_id']: n for n in nodes}
    for revision, visible in approved.items():
        if revision not in current or d2k.catalog_nodes([current[revision]])[0] != visible:
            fail('d2k_authorized_knowledge_changed')
    if history:
        own = conn.execute('''SELECT DISTINCT r.result_node_revision_id FROM compiler_runtime.k_compilation_records r
            JOIN compiler_runtime.d2k_execution_authorizations a USING(execution_id)
            WHERE a.authorization_id=%s AND r.disposition IN ('accepted_new','reused')''', (authorization_id,)).fetchall()
        for row in own:
            revision = str(row['result_node_revision_id'])
            if revision not in current:
                fail('d2k_authorized_knowledge_changed')
            approved[revision] = d2k.catalog_nodes([current[revision]])[0]
    context = {key: grant[key] for key in ('authorization_id','preparation_id','manifest_sha256','actor_ref')}
    context['failure'] = deepcopy(manifest['failure'])
    feedback = None
    if prior_execution_id:
        from .knowledge_runtime import KnowledgeRuntime
        previous = KnowledgeRuntime._job(conn, prior_execution_id)
        feedback = {'execution_id':prior_execution_id,'state':previous['state'],
            'generator_reviews':(previous['generator_receipt'] or {}).get('view_reviews',[]),
            'validator_reviews':(previous['validator_receipt'] or {}).get('d2k_view_reviews',[]),
            'records':json.loads(json.dumps(KnowledgeRuntime._records(conn,prior_execution_id),default=str))}
    return context, [current[key] for key in sorted(approved)], feedback


class D2KRuntime:
    def __init__(self, dsn, artifact_root):
        self.dsn=dsn
        self.artifacts=ArtifactStore(artifact_root)
        self.derived=ArtifactStore(Path(artifact_root)/'derived')
        self.repository=PostgresRepository(dsn)

    def export_source(self, data_id, destination):
        registered=self.repository.get_data(check_data_id(data_id))
        if registered is None:
            fail('data_not_found',2)
        raw=self.artifacts.read(data_id,registered['byte_size'])
        target=Path(destination)
        with target.open('xb') as stream:
            stream.write(raw)
        return {'data_id':data_id,'byte_size':len(raw),'path':str(target),
                'd2i_calls':0,'information_writes':0,'actual_delivery':False}

    def draft(self, data_id, identifier, *, reason, failure_execution_id=None,
              byte_ranges=None, pdf_directory=None, data_version_ids=None, data_version_mode='current'):
        from .knowledge_runtime import KnowledgeRuntime, MODEL
        from .information_errors import report
        data_id,identifier=check_data_id(data_id),request_id(identifier)
        if not isinstance(reason,str) or not reason.strip() or '\x00' in reason:
            fail('d2k_issue_description_required',2)
        if (data_version_mode not in ('current','pinned')
                or (data_version_ids is None and data_version_mode!='current')):
            fail('invalid_data_version_context',2)
        registered=self.repository.get_data(data_id)
        if registered is None:
            fail('data_not_found',2)
        failure={'kind':'user_reported_d2i_issue','reason':reason,'execution_id':None,
                 'verification_status':'user_reported_not_independently_verified'}
        with connection(self.dsn) as conn:
            if not available(conn):
                fail('d2k_schema_required',3)
            if failure_execution_id is not None:
                failure_execution_id=request_id(failure_execution_id)
                execution=conn.execute('SELECT operation,data_id,state,error_code FROM compiler_runtime.operation_executions WHERE execution_id=%s',
                                       (failure_execution_id,)).fetchone()
                if execution is None:
                    fail('d2k_failure_context_missing',2)
                if execution['operation']=='d2i':
                    if execution['data_id']!=data_id or execution['state'] not in ('failed','needs_human'):
                        fail('d2k_failure_context_mismatch',2)
                    failure.update(kind='recorded_d2i_failure',execution_id=failure_execution_id,
                        state=execution['state'],error_code=execution['error_code'],verification_status='recorded_execution_state')
                elif execution['operation']=='i2k':
                    errors=report(KnowledgeRuntime(self.dsn).show(failure_execution_id))
                    related=[item for item in errors['errors'] if item['data_id']==data_id]
                    if not related:
                        fail('d2k_failure_context_mismatch',2)
                    failure.update(kind='recorded_information_error',execution_id=failure_execution_id,
                        information_errors=related,verification_status='reported_error_not_repaired')
                else:
                    fail('d2k_failure_context_mismatch',2)
            versions=immutable_versions(conn,data_version_ids) if data_version_ids is not None else []
            if versions and {value['data_id'] for value in versions}!={data_id}:
                fail('data_version_source_mismatch',2)
        raw=self.artifacts.read(data_id,registered['byte_size'])
        selectors={'byte_ranges':byte_ranges,'pdf_manifest_sha256':None}
        pdf_manifest=None
        if registered['media_type']=='application/pdf':
            if byte_ranges is not None or pdf_directory is None:
                fail('d2k_pdf_views_required',2)
            from .d2k_pdf import verify_source
            with tempfile.TemporaryDirectory(prefix='palimpsest-d2k-original-') as temporary:
                original=Path(temporary)/'original.pdf'
                original.write_bytes(raw)
                pdf_manifest=verify_source(original,Path(pdf_directory),data_id,expected_byte_size=len(raw))
            selectors['pdf_manifest_sha256']=digest(pdf_manifest)
        elif pdf_directory is not None:
            fail('d2k_text_views_required',2)
        else:
            if not d2k._text_media(registered['media_type']):
                fail('d2k_unsupported_media',2)
            byte_ranges=[[0,len(raw)]] if byte_ranges is None else byte_ranges
            if (not isinstance(byte_ranges,list) or not byte_ranges
                    or any(not isinstance(item,(list,tuple)) or len(item)!=2 for item in byte_ranges)):
                fail('invalid_d2k_text_range',2)
            selectors['byte_ranges']=[list(item) for item in byte_ranges]
        request={'data_id':data_id,'reason':reason,'failure':failure,'selectors':selectors,
                 'model':dict(MODEL),'data_versions':versions,'data_version_mode':data_version_mode}
        fingerprint=digest(request)
        with connection(self.dsn) as conn,conn.transaction():
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('d2k-draft:'+identifier,))
            prior=conn.execute('SELECT * FROM compiler_runtime.d2k_preparations WHERE preparation_id=%s',(identifier,)).fetchone()
            if prior:
                if prior['request_fingerprint']!=fingerprint:
                    fail('idempotency_conflict')
                return self._summary(prior,True)
            views=[]
            if pdf_manifest is None:
                for start,end in byte_ranges:
                    view_id=str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
                    views.append(d2k.text_view(raw,view_id=view_id,data_id=data_id,byte_start=start,byte_end=end))
            else:
                for page in pdf_manifest['pages']:
                    view_id=str(conn.execute('SELECT uuidv7() AS id').fetchone()['id'])
                    image_path=Path(pdf_directory)/page['png']['path']
                    image=image_path.read_bytes()
                    if sha256(image).hexdigest()!=page['png']['sha256'] or len(image)!=page['png']['byte_size']:
                        fail('d2k_pdf_view_changed')
                    with self.derived.request_lock(view_id):
                        staged=self.derived.stage(image_path,view_id)
                        if staged.data_id!=page['png']['sha256'] or staged.byte_size!=len(image):
                            fail('d2k_pdf_view_changed')
                        self.derived.publish(view_id,staged.data_id,staged.byte_size)
                        self.derived.cleanup(view_id)
                    views.append({'kind':'pdf_page','view_id':view_id,'data_id':data_id,'original_byte_size':len(raw),
                        'page_index':page['page_index'],'page_count':pdf_manifest['source']['page_count'],
                        'page_size':page['source_geometry']['size'],'image_sha256':page['png']['sha256'],
                        'image_byte_size':page['png']['byte_size'],'source_geometry':page['source_geometry'],
                        'transforms':page['transforms'],'renderer':pdf_manifest['renderer']})
            packet=d2k.build_input(data_id,media_type=registered['media_type'],original_byte_size=len(raw),views=views)
            conn.execute('SELECT version FROM compiler_runtime.knowledge_state WHERE singleton FOR SHARE')
            catalog=d2k.catalog_nodes(KnowledgeRuntime._nodes(conn))
            manifest={'schema_version':MANIFEST,'operation':'d2k','preparation_id':identifier,'data_id':data_id,
                'input':packet,'model':dict(MODEL),'failure':failure,'data_versions':versions,
                'data_version_mode':data_version_mode,'allowed_phases':['generator','validator','same_scope_review'],
                'claim_policy':'explicit_source_content_only','new_inference_allowed':False,
                'd2i_repair_allowed':False,'information_created':0,'pdf_verification':pdf_manifest,
                'existing_knowledge':catalog}
            conn.execute('''INSERT INTO compiler_runtime.d2k_preparations
                (preparation_id,request_fingerprint,data_id,packet,manifest,manifest_sha256)
                VALUES (%s,%s,%s,%s,%s,%s)''',(identifier,fingerprint,data_id,Jsonb(packet),Jsonb(manifest),digest(manifest)))
            for ordinal,view in enumerate(views):
                conn.execute('INSERT INTO compiler_runtime.d2k_source_views(preparation_id,view_id,ordinal,body) VALUES (%s,%s,%s,%s)',
                             (identifier,view['view_id'],ordinal,Jsonb(view)))
        return self._summary({'preparation_id':identifier,'data_id':data_id,'manifest':manifest,'manifest_sha256':digest(manifest)},False)

    @staticmethod
    def _summary(row,replayed=False):
        manifest=row['manifest']
        return {'preparation_id':str(row['preparation_id']),'data_id':row['data_id'],
            'manifest_sha256':row['manifest_sha256'],'view_count':len(manifest['input']['views']),
            'existing_knowledge_count':len(manifest.get('existing_knowledge',[])),
            'state':'awaiting_explicit_user_confirmation','model':manifest['model'],'failure':manifest['failure'],
            'actual_delivery':False,'d2i_calls':0,'information_writes':0,'replayed':replayed}

    def preparation(self, identifier):
        with connection(self.dsn) as conn:
            if not available(conn):
                fail('d2k_schema_required',3)
            row=conn.execute('SELECT * FROM compiler_runtime.d2k_preparations WHERE preparation_id=%s',(request_id(identifier),)).fetchone()
        if row is None:
            fail('d2k_preparation_not_found',2)
        if row['manifest_sha256']!=digest(row['manifest']) or row['manifest']['input']!=row['packet']:
            fail('d2k_preparation_changed')
        return json.loads(json.dumps(row,default=str))

    def authorize(self, preparation_id, authorization_id, confirmation_sha256, *, actor_ref):
        """Trusted local CLI command, never dispatched from provider output."""
        preparation=self.preparation(preparation_id)
        identifier=request_id(authorization_id)
        if (not isinstance(actor_ref,str) or not actor_ref.strip() or '\x00' in actor_ref
                or confirmation_sha256!=preparation['manifest_sha256']):
            fail('d2k_exact_confirmation_required',2)
        with connection(self.dsn) as conn,conn.transaction():
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('d2k-authorization:'+identifier,))
            old=conn.execute('SELECT * FROM compiler_runtime.d2k_authorizations WHERE authorization_id=%s',(identifier,)).fetchone()
            if old:
                if (str(old['preparation_id'])!=preparation_id or old['manifest_sha256']!=confirmation_sha256
                        or old['actor_ref']!=actor_ref):
                    fail('idempotency_conflict')
            else:
                conn.execute('''INSERT INTO compiler_runtime.d2k_authorizations
                    (authorization_id,preparation_id,manifest_sha256,actor_ref,confirmation_method)
                    VALUES (%s,%s,%s,%s,'explicit_local_cli_manifest')''',
                    (identifier,preparation_id,confirmation_sha256,actor_ref))
        return {'authorization_id':identifier,'preparation_id':preparation_id,'manifest_sha256':confirmation_sha256,
            'actor_ref':actor_ref,'operation':'d2k','replayed':old is not None,'model_calls':0}

    def prepare(self, authorization_id, identifier, *, prior_execution_id=None):
        from .knowledge_runtime import KnowledgeRuntime
        with connection(self.dsn) as conn:
            grant=load_authorization(conn,authorization_id)
        packet,manifest=grant['packet'],grant['manifest']
        self._verify_artifacts(packet)
        options={'model_profile':manifest['model'],'authorization_id':authorization_id,
                 'retry_of_execution_id':prior_execution_id}
        if manifest['data_versions']:
            options.update(data_version_ids=[v['version_id'] for v in manifest['data_versions']],
                           data_version_mode=manifest['data_version_mode'])
        return KnowledgeRuntime(self.dsn).prepare('d2k',packet['data_id'],request_id(identifier),packet,**options)

    def _verify_artifacts(self, packet):
        d2k.check_input(packet)
        raw=self.artifacts.read(packet['data_id'],packet['original_byte_size'])
        for view in packet['views']:
            if view['kind']=='text':
                if d2k.text_view(raw,view_id=view['view_id'],data_id=packet['data_id'],
                    byte_start=view['locator']['byte_start'],byte_end=view['locator']['byte_end'])!=view:
                    fail('d2k_original_view_changed')
            else:
                self.derived.read(view['image_sha256'],view['image_byte_size'])

    def prepare_call(self, execution_id, phase, directory):
        from .knowledge_runtime import KnowledgeRuntime
        from .paper_wiki_runtime import _image_suffix
        from .wiki_projection_store import ProjectionStore
        if phase not in ('generator','validator'):
            fail('invalid_knowledge_phase',2)
        runtime=KnowledgeRuntime(self.dsn)
        job=runtime.show(execution_id)
        if job['operation']!='d2k' or job['state']!=('prepared' if phase=='generator' else 'proposed'):
            fail('d2k_call_not_ready')
        self._verify_artifacts(job['input_snapshot']['input'])
        output=ProjectionStore(Path(directory))
        assets,images,seen=[],[],set()
        with output.locked():
            for view in job['input_snapshot']['input']['views']:
                if view['kind']=='text' or view['image_sha256'] in seen:
                    continue
                key=view['image_sha256'];seen.add(key)
                raw=self.derived.read(key,view['image_byte_size'])
                path='media/'+key+_image_suffix(raw)
                output.write_bytes(path,raw)
                assets.append({'sha256':key,'byte_size':len(raw)})
                images.append({'path':path,'sha256':key})
            context=job if phase=='generator' else runtime.validation_context(execution_id)
            prompt=d2k.generation(job['input_snapshot'],assets) if phase=='generator' else d2k.validation(context,assets)
            schema=d2k.generation_schema(job['input_snapshot']['input']) if phase=='generator' else d2k.validation_schema(
                [node['candidate_key'] for node in context['candidates']],
                [node['knode_revision_id'] for node in job['input_snapshot']['existing_nodes']],job['input_snapshot']['input'])
            value={'prompt':prompt,'schema':schema,'images':images,'input_sha256':job['input_digest'] if phase=='generator'
                else context['validation_context_sha'],'output_file':phase+'-response.json',
                'delivered_data_view_ids':d2k.check_input(job['input_snapshot']['input']),
                'delivered_knowledge_revision_ids':[n['knode_revision_id'] for n in job['input_snapshot']['existing_nodes']]}
            if job['input_snapshot'].get('data_versions'):
                value['delivered_data_version_ids']=[v['version_id'] for v in job['input_snapshot']['data_versions']]
            binding={'execution_id':execution_id,'phase':phase,'profile':job['profile'],'request_sha256':digest(value)}
            prior=output.read_json(phase+'-binding.json')
            if prior is not None and (prior!=binding or output.read_json(phase+'-request.json')!=value):
                fail('d2k_call_directory_conflict')
            if prior is None:
                output.write_json(phase+'-request.json',value);output.write_json(phase+'-binding.json',binding)
        return {'execution_id':execution_id,'phase':phase,'request_file':str(output.root/(phase+'-request.json')),
                'actual_delivery':False,'replayed':prior is not None}
