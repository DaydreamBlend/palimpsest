"""Durable execution and atomic effects for the first D2I vertical slice.

Source D2I performs only deterministic assembly and structural verification.
Legacy receipts remain readable for historical experiments. Parser blobs are
published before their immutable manifest is referenced by PostgreSQL.
"""

from copy import deepcopy
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import tempfile

from psycopg.types.json import Jsonb

from .artifact_store import ArtifactStore, _directory, _file, _read_payload
from .canonical_store import connection, PostgresRepository
from .data import data_id as validate_data_id, request_id
from .errors import PalimpsestError
from .information import validate_proposal, validate_decisions, fingerprints
from .d2i import build_units, verify_units, assembly_payload, text_assemblies, SOURCE_ALGORITHMS, SOURCE_GROUPS_VERSION, SOURCE_GROUPS_V2_VERSION, SOURCE_PAGE_GROUPS_VERSION, MARKDOWN_ALGORITHM, CODE_ALGORITHM, TEXT_ALGORITHMS
from .mineru_adapter import normalize_middle
from .paddle_adapter import normalize_paddle
from .figure_adapter import attach_figures, INVENTORY_NAME
from .figure_coverage import figure_coverage
from .source_units import SOURCE_UNITS_VERSION
from .information import SOURCE_SCHEMA_VERSION
from .hybrid_profile import HYBRID_PARSER, matches_hybrid_parser, matches_dual_parser, matches_image_parser
from .hybrid_receipt import validate_hybrid_receipt

SOURCE_PROFILE = 'source-d2i-v1'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def fail(code, exit_code=4):
    raise PalimpsestError(code, 'D2I 작업 상태와 입력을 확인하세요.', exit_code)


def validate_profile(profile):
    if not isinstance(profile, dict) or profile.get('schema_version') not in ('d2i-v1', SOURCE_PROFILE):
        fail('invalid_compilation_profile', 2)
    parser = profile.get('parser', {})
    if not isinstance(parser, dict):
        fail('invalid_compilation_profile', 2)
    from .markdown_adapter import MARKDOWN_PARSER
    from .code_adapter import CODE_PARSER
    markdown = profile['schema_version'] == SOURCE_PROFILE and parser == MARKDOWN_PARSER
    code = profile['schema_version'] == SOURCE_PROFILE and parser == CODE_PARSER
    mineru = (parser.get('provider') == 'mineru' and parser.get('version') == '3.4.5'
              and parser.get('backend') == 'pipeline'
              and parser.get('adapter_version') != 'mineru-hybrid-preproc-v1')
    hybrid = (profile['schema_version'] == SOURCE_PROFILE
              and (matches_hybrid_parser(parser) or matches_dual_parser(parser) or matches_image_parser(parser)))
    paddle = (profile['schema_version'] == SOURCE_PROFILE
              and parser.get('provider') == 'paddleocr-vl' and parser.get('version') == '3.7.0'
              and parser.get('backend') == 'transformers' and parser.get('pipeline_version') == 'v1.6'
              and parser.get('adapter_version') == 'paddleocr-raw-v1')
    if (not (mineru or hybrid or paddle or markdown or code) or (not (markdown or code) and (
            not parser.get('image_digest') or not parser.get('models_manifest_sha256')))):
        fail('invalid_compilation_profile', 2)
    if not isinstance(profile.get('policy'), dict):
        fail('invalid_compilation_profile', 2)
    if profile['schema_version'] == SOURCE_PROFILE:
        if (set(profile) != {'schema_version', 'parser', 'transformation', 'policy'}
                or profile['transformation'] not in [
                    {'algorithm': algorithm, 'schema_version': SOURCE_SCHEMA_VERSION}
                    for algorithm in ((CODE_ALGORITHM,) if code else (MARKDOWN_ALGORITHM,) if markdown else SOURCE_ALGORITHMS)]
                or profile['policy'].get('llm_calls') != 0
                or profile['policy'].get('source_fidelity') != 'source_preserving'
                or profile['policy'].get('extraction_scope') != 'whole_document'):
            fail('invalid_compilation_profile', 2)
        digest(profile)
        origin = profile['policy'].get('source_reassembly')
        if origin is not None:
            if (profile['transformation']['algorithm'] not in (SOURCE_GROUPS_VERSION, SOURCE_GROUPS_V2_VERSION)
                    or not isinstance(origin, dict) or set(origin) != {
                        'source_execution_id', 'source_profile_sha256', 'source_parse_manifest_sha256'}):
                fail('invalid_compilation_profile', 2)
            request_id(origin['source_execution_id'])
            validate_data_id(origin['source_profile_sha256'])
            validate_data_id(origin['source_parse_manifest_sha256'])
        page_origin = profile['policy'].get('source_page_origin')
        if profile['transformation']['algorithm'] == SOURCE_PAGE_GROUPS_VERSION:
            if (origin is not None or not isinstance(page_origin, dict) or set(page_origin) != {
                    'source_execution_id','source_profile_sha256','source_parse_manifest_sha256','evidence_manifest_sha256'}):
                fail('invalid_compilation_profile', 2)
            request_id(page_origin['source_execution_id'])
            for key in ('source_profile_sha256','source_parse_manifest_sha256','evidence_manifest_sha256'):
                validate_data_id(page_origin[key])
        elif page_origin is not None:
            fail('invalid_compilation_profile', 2)
        return profile
    # Compatibility for historical snapshot tests; the public CLI rejects this path.
    for role in ('generator', 'validator'):
        model = profile.get(role, {})
        if any(model.get(key) != value for key, value in {
            'provider':'codex_cli', 'model':'gpt-5.6-terra',
            'reasoning_effort':'medium', 'auth':'chatgpt_oauth', 'cli_version':'0.153.4'
        }.items()):
            fail('invalid_compilation_profile', 2)
    if not isinstance(profile.get('policy'), dict):
        fail('invalid_compilation_profile', 2)
    digest(profile)
    return profile




class CompilerRuntime:
    def __init__(self, dsn, artifact_root):
        self.dsn = dsn
        self.store = ArtifactStore(Path(artifact_root))
        self.derived = ArtifactStore(Path(artifact_root) / 'derived')
        self.data = PostgresRepository(dsn)

    @staticmethod
    def _event(conn, job, state, error=None):
        conn.execute('''INSERT INTO compiler_runtime.execution_events
            (execution_id,attempt,state,error_code) VALUES (%s,%s,%s,%s)''',
            (job['execution_id'], job['attempt'], state, error))

    @staticmethod
    def _job(conn, execution_id, lock=False):
        row = conn.execute('''SELECT e.*,p.payload AS profile FROM compiler_runtime.operation_executions e
            JOIN compiler_runtime.profiles p USING(profile_id) WHERE execution_id=%s'''
            + (' FOR UPDATE OF e' if lock else ''), (request_id(str(execution_id)),)).fetchone()
        if row is None:
            fail('job_not_found', 2)
        return row

    def start(self, data_id, profile, generation=1):
        validate_data_id(data_id)
        validate_profile(profile)
        if type(generation) is not int or generation < 1:
            fail('invalid_generation', 2)
        data = self.data.get_data(data_id)
        text_source = profile.get('transformation', {}).get('algorithm') in TEXT_ALGORITHMS
        if not data or data['media_type'] != ('text/markdown' if text_source else 'application/pdf'):
            fail('markdown_data_required' if text_source else 'pdf_data_required', 2)
        self.store.verify(data_id, data['byte_size'])
        with connection(self.dsn) as conn, conn.transaction():
            from .realm_registration import verify_ready
            verify_ready(conn, [data_id])
            conn.execute('INSERT INTO compiler_runtime.profiles(profile_hash,payload) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                         (digest(profile), Jsonb(profile)))
            profile_id = conn.execute('SELECT profile_id FROM compiler_runtime.profiles WHERE profile_hash=%s',
                                      (digest(profile),)).fetchone()['profile_id']
            created = conn.execute('''INSERT INTO compiler_runtime.operation_executions(operation,data_id,profile_id,generation)
                VALUES ('d2i',%s,%s,%s) ON CONFLICT DO NOTHING RETURNING *''',
                (data_id,profile_id,generation)).fetchone()
            job = created or conn.execute('''SELECT * FROM compiler_runtime.operation_executions
                WHERE operation='d2i' AND data_id=%s AND profile_id=%s AND generation=%s''',
                (data_id,profile_id,generation)).fetchone()
            if created:
                self._event(conn, job, 'prepared')
            return {'execution_id':job['execution_id'], 'data_id':data_id,
                    'state':job['state'], 'replayed':created is None}

    def show(self, execution_id, *, include_input=False):
        with connection(self.dsn) as conn:
            job = self._job(conn, execution_id)
            records = conn.execute('''SELECT record_id,ordinal,disposition,reason_codes,result_information_id,
                identity_fingerprint,content_fingerprint,context_fingerprint FROM compiler_runtime.records
                WHERE execution_id=%s ORDER BY ordinal''', (execution_id,)).fetchall()
            events = conn.execute('''SELECT attempt,state,error_code,created_at FROM compiler_runtime.execution_events
                WHERE execution_id=%s ORDER BY event_id''', (execution_id,)).fetchall()
            result = {**job, 'records':records, 'events':events,
                      'information_ids':[r['result_information_id'] for r in records if r['result_information_id']]}
            if include_input:
                parsed = conn.execute('SELECT * FROM compiler_runtime.parse_artifacts WHERE execution_id=%s', (execution_id,)).fetchone()
                candidates = conn.execute('''SELECT c.body FROM compiler_runtime.temporary_candidates c
                    JOIN compiler_runtime.records r USING(record_id) WHERE r.execution_id=%s ORDER BY r.ordinal''',
                    (execution_id,)).fetchall()
                result['parse'] = parsed
                result['proposals'] = [c['body'] for c in candidates]
            return result

    def compile_markdown(self, data_id, *, generation=1, checkpoint=None):
        """Compile registered Markdown bytes with deterministic structural grouping."""
        from .markdown_adapter import MARKDOWN_PARSER
        return self._compile_text(data_id, MARKDOWN_PARSER, MARKDOWN_ALGORITHM,
            ('markdown_adapter.py', 'information.py', 'd2i.py', 'compiler_runtime.py'),
            generation=generation, checkpoint=checkpoint)

    def compile_code(self, data_id, *, generation=1, checkpoint=None):
        """Explicit native parsing of a registered exact code snapshot."""
        from .code_adapter import CODE_PARSER
        return self._compile_text(data_id, CODE_PARSER, CODE_ALGORITHM,
            ('code_adapter.py', 'code_snapshot.py', 'information.py', 'd2i.py', 'compiler_runtime.py'),
            generation=generation, checkpoint=checkpoint)

    def _compile_text(self, data_id, parser, algorithm, implementation_files, *, generation, checkpoint):
        profile = {'schema_version': SOURCE_PROFILE, 'parser': deepcopy(parser),
                   'transformation': {'algorithm': algorithm, 'schema_version': SOURCE_SCHEMA_VERSION},
                   'policy': {'version': SOURCE_PROFILE, 'llm_calls': 0, 'source_fidelity': 'source_preserving',
                              'extraction_scope': 'whole_document', 'implementation_sha256': {
                                  name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                  for name in implementation_files}}}
        job = self.start(data_id, profile, generation)
        execution_id = str(job['execution_id'])
        try:
            result = self.materialize_source(execution_id, checkpoint=checkpoint)
        except PalimpsestError as error:
            self.mark_failed(execution_id, error.code)
            raise
        if result['state'] == 'completed' and 'information_ids' not in result:
            result['information_ids'] = self.show(execution_id)['information_ids']
        return {**result, 'data_id': data_id, 'source_algorithm': algorithm,
                'llm_calls': 0, 'ocr_calls': 0}

    def _attach_markdown(self, job):
        from .markdown_adapter import parse_markdown
        from .code_adapter import parse_code_snapshot
        native = job['profile']['transformation']['algorithm'] == CODE_ALGORITHM
        data = self.data.get_data(job['data_id'])
        raw = self.store.read(job['data_id'], data['byte_size'])
        bundle = (parse_code_snapshot if native else parse_markdown)(raw, data_id=job['data_id'])
        entry = 'code_parse.json' if native else 'markdown_parse.json'
        with tempfile.TemporaryDirectory(prefix='palim-markdown-') as temporary:
            path = Path(temporary) / entry
            path.write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True), encoding='utf-8')
            parsed = self._publish(path)
        manifest = {'schema_version': 1, 'data_id': job['data_id'], 'middle': entry,
                    'profile': job['profile']['parser'], 'files': {entry: parsed},
                    'bundle_sha256': digest(bundle)}
        return self._save_parse(str(job['execution_id']), bundle, manifest)

    def _publish(self, source):
        identifier = self.data.allocate_id()
        with self.derived.request_lock(identifier):
            payload = self.derived.stage(source, identifier)
            self.derived.publish(identifier, payload.data_id, payload.byte_size)
            self.derived.cleanup(identifier)
        return {'sha256':payload.data_id, 'byte_size':payload.byte_size,
                'artifact_path':f'derived/objects/sha256/{payload.data_id[:2]}/{payload.data_id}'}

    def export_parser(self, execution_id, directory):
        """Materialize retained parser files after a host scratch directory is lost."""
        with connection(self.dsn) as conn:
            self._job(conn,execution_id)
            parsed=conn.execute('SELECT manifest,manifest_hash FROM compiler_runtime.parse_artifacts WHERE execution_id=%s',(execution_id,)).fetchone()
        if not parsed or digest(parsed['manifest'])!=parsed['manifest_hash']:
            fail('parser_manifest_missing')
        target=Path(directory).absolute()
        target.mkdir(parents=True,exist_ok=True)
        if target.is_symlink():
            fail('unsafe_export_path')
        for name,reference in parsed['manifest']['files'].items():
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts:
                fail('unsafe_export_path')
            destination=target/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.resolve().is_relative_to(target.resolve()) or destination.is_symlink():
                fail('unsafe_export_path')
            source=self.derived.root/'objects'/'sha256'/reference['sha256'][:2]/reference['sha256']
            with _directory(source.parent) as parent, _file(parent,source.name) as descriptor:
                payload=_read_payload(descriptor,parent,source.name)
                if payload.data_id!=reference['sha256'] or payload.byte_size!=reference['byte_size']:
                    fail('integrity_conflict',6)
                if destination.exists():
                    if sha256(destination.read_bytes()).hexdigest()!=payload.data_id:
                        fail('export_conflict',6)
                    continue
                os.lseek(descriptor,0,os.SEEK_SET)
                temporary=None
                try:
                    with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as output:
                        temporary=Path(output.name)
                        while chunk:=os.read(descriptor,1024*1024):
                            output.write(chunk)
                        output.flush()
                        os.fsync(output.fileno())
                    if sha256(temporary.read_bytes()).hexdigest()!=payload.data_id:
                        fail('integrity_conflict',6)
                    os.link(temporary,destination)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
        return {'execution_id':execution_id,'file_count':len(parsed['manifest']['files']),
                'middle':parsed['manifest']['middle']}

    def attach_parser(self, execution_id, directory, middle_name, expected_pages):
        job = self.show(execution_id)
        if job['profile'].get('transformation', {}).get('algorithm') in TEXT_ALGORITHMS:
            fail('registered_markdown_required', 2)
        if 'source_reassembly' in job['profile']['policy'] or 'source_page_origin' in job['profile']['policy']:
            fail('retained_source_required', 2)
        directory = Path(directory).resolve(strict=True)
        # Each provider validates its own untouched raw schema and crop references.
        paddle = job['profile']['parser']['provider'] == 'paddleocr-vl'
        if (Path(middle_name).name != middle_name
                or (middle_name != 'paddle_raw.json' if paddle else not middle_name.endswith('_middle.json'))):
            fail('invalid_parser_output')
        middle_path = directory / middle_name
        if middle_path.is_symlink():
            fail('invalid_parser_output')
        middle_bytes = middle_path.read_bytes()
        middle_hash = sha256(middle_bytes).hexdigest()
        middle = json.loads(middle_bytes)
        hybrid_artifacts = None
        dual = matches_dual_parser(job['profile']['parser'])
        image = matches_image_parser(job['profile']['parser'])
        if job['profile']['parser'].get('adapter_version') == 'mineru-hybrid-preproc-v1' or dual or image:
            receipt_path = directory / 'palimpsest_source_check.json'
            if not receipt_path.is_file() or receipt_path.is_symlink():
                fail('parser_source_check_missing')
            receipt_bytes = receipt_path.read_bytes()
            receipt = json.loads(receipt_bytes)
            hybrid_artifacts = validate_hybrid_receipt(receipt,
                profile=job['profile'], data_id=job['data_id'], middle_name=middle_name, expected_pages=expected_pages)
            retained_profile = directory / 'palimpsest_profile.json'
            if retained_profile.is_symlink() or digest(json.loads(retained_profile.read_bytes())) != digest(job['profile']):
                fail('parser_profile_mismatch')
        normalize = normalize_paddle if paddle else normalize_middle
        normalization_arguments = {}
        if dual:
            from .dual_adapter import normalize_dual
            normalize = normalize_dual
            normalization_arguments['receipt'] = receipt
        elif image:
            from .image_adapter import normalize_image
            normalize = normalize_image
            normalization_arguments['receipt'] = receipt
        bundle = normalize(middle, data_id=job['data_id'], artifact_root=directory,
                           expected_pages=expected_pages, profile=job['profile']['parser'], **normalization_arguments)
        if hybrid_artifacts is not None and (
                [page['page_idx'] for page in middle['pdf_info']] != list(range(expected_pages))
                or [page['page_size'] for page in middle['pdf_info']] != receipt['parser_page_sizes']):
            fail('invalid_parser_output')
        figure_digest = job['profile']['policy'].get('figure_inventory_sha256')
        if figure_digest is not None:
            bundle = attach_figures(bundle, artifact_root=directory,
                                    expected_sha256=figure_digest, middle_sha256=middle_hash)
            if (job['profile']['schema_version'] == SOURCE_PROFILE
                    and bundle.get('extraction_scope') != 'whole_document'):
                fail('source_scope_mismatch', 2)
            figure_coverage(bundle, None)
        manifest_files = {}
        for path in sorted(directory.rglob('*')):
            if path.is_symlink():
                fail('invalid_parser_output')
            if path.is_file():
                manifest_files[path.relative_to(directory).as_posix()] = self._publish(path)
        if manifest_files.get(middle_name, {}).get('sha256') != middle_hash:
            fail('parser_artifact_changed')
        if hybrid_artifacts is not None:
            if (set(manifest_files) != set(hybrid_artifacts) | {'palimpsest_source_check.json'}
                    or manifest_files['palimpsest_source_check.json']['sha256'] != sha256(receipt_bytes).hexdigest()):
                fail('parser_artifact_changed')
            for name, item in hybrid_artifacts.items():
                if (manifest_files[name]['sha256'] != item['sha256']
                        or manifest_files[name]['byte_size'] != item['bytes']):
                    fail('parser_artifact_changed')
        if figure_digest is not None and manifest_files.get(INVENTORY_NAME, {}).get('sha256') != figure_digest:
            fail('parser_artifact_changed')
        for block in bundle['blocks']:
            for image in block['image_paths']:
                if manifest_files.get(image['path'], {}).get('sha256') != image['sha256']:
                    fail('parser_artifact_changed')
        manifest = {'schema_version':1, 'data_id':job['data_id'], 'middle':middle_name,
                    'profile':job['profile']['parser'], 'files':manifest_files, 'bundle_sha256':digest(bundle)}
        return self._save_parse(execution_id, bundle, manifest)

    def _save_parse(self, execution_id, bundle, manifest):
        with tempfile.TemporaryDirectory(prefix='palim-manifest-') as tmp:
            path = Path(tmp) / 'manifest.json'
            path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding='utf-8')
            published = self._publish(path)
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn, execution_id, lock=True)
            existing = conn.execute('SELECT manifest_hash FROM compiler_runtime.parse_artifacts WHERE execution_id=%s', (execution_id,)).fetchone()
            if existing:
                if existing['manifest_hash'] != digest(manifest):
                    fail('parser_retry_conflict', 6)
                return {'execution_id':execution_id,'state':job['state'],'replayed':True}
            if job['state'] != 'prepared':
                fail('job_not_ready', 7)
            conn.execute('''INSERT INTO compiler_runtime.parse_artifacts
                (execution_id,data_id,manifest_hash,artifact_path,manifest,bundle) VALUES (%s,%s,%s,%s,%s,%s)''',
                (execution_id,job['data_id'],digest(manifest),published['artifact_path'],Jsonb(manifest),Jsonb(bundle)))
            conn.execute("UPDATE compiler_runtime.operation_executions SET state='parsed',updated_at=clock_timestamp() WHERE execution_id=%s", (execution_id,))
            self._event(conn,job,'parsed')
        return {'execution_id':execution_id,'state':'parsed','replayed':False}

    @staticmethod
    def _receipt(receipt, role, job):
        if job['profile']['schema_version'] == SOURCE_PROFILE:
            if (not isinstance(receipt,dict) or receipt.get('receipt_kind') != 'deterministic_source_check'
                    or receipt.get('algorithm') != job['profile']['transformation']['algorithm']
                    or receipt.get('role') != ('source_builder' if role == 'generator' else 'source_checker')
                    or receipt.get('llm_calls') != 0 or 'thread_ref' in receipt):
                fail('invalid_source_receipt')
            return
        if not isinstance(receipt,dict) or not isinstance(receipt.get('profile'),dict):
            fail('invalid_provider_receipt')
        for key, value in job['profile'][role].items():
            if receipt['profile'].get(key) != value:
                fail('provider_profile_mismatch')
        if not receipt.get('thread_ref'):
            fail('invalid_provider_receipt')
        if receipt.get('prompt_version') != job['profile']['policy'].get(role+'_prompt'):
            fail('provider_prompt_mismatch')
        if role == 'validator' and receipt['thread_ref'] == job['generator_receipt']['thread_ref']:
            fail('validator_not_independent')

    def propose(self, execution_id, proposals, receipt):
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn, execution_id, lock=True)
            self._receipt(receipt,'generator',job)
            if receipt.get('output_sha256') != digest({'proposals':proposals}):
                fail('provider_receipt_mismatch')
            if job['generator_receipt'] is not None:
                if job['generator_receipt'] != receipt:
                    fail('proposal_retry_conflict',6)
                return {'execution_id':execution_id,'state':job['state'],'replayed':True}
            if job['state'] != 'parsed' or not isinstance(proposals,list):
                fail('job_not_ready',7)
            parsed = conn.execute('SELECT bundle FROM compiler_runtime.parse_artifacts WHERE execution_id=%s', (execution_id,)).fetchone()['bundle']
            if receipt.get('source_bundle_sha256') != digest(parsed):
                fail('provider_source_mismatch')
            blocks = {b['block_id']:b for b in parsed['blocks']}
            normalized = [validate_proposal(p,blocks) for p in proposals]
            if job['profile']['schema_version'] == SOURCE_PROFILE:
                checks = verify_units(parsed, normalized, job['profile']['transformation']['algorithm'])
                if receipt != self._source_receipt('generator', parsed, normalized, checks):
                    fail('invalid_source_receipt')
            if job['profile']['schema_version'] != SOURCE_PROFILE or job['profile']['transformation']['algorithm'] not in TEXT_ALGORITHMS:
                figure_coverage(parsed, normalized)
            # Bind transport receipt to frozen candidates; a later retry cannot swap them.
            for ordinal, proposal in enumerate(normalized):
                fp = fingerprints(job['data_id'],proposal,blocks)
                context = digest({'domain':fp['context_fingerprint'],'profiles':job['profile']})
                record_id = conn.execute('''INSERT INTO compiler_runtime.records
                    (subtype,execution_id,data_id,ordinal,identity_fingerprint,content_fingerprint,context_fingerprint)
                    VALUES ('D2IRecord',%s,%s,%s,%s,%s,%s) RETURNING record_id''',
                    (execution_id,job['data_id'],ordinal,fp['identity_fingerprint'],fp['content_fingerprint'],context)).fetchone()['record_id']
                conn.execute('INSERT INTO compiler_runtime.temporary_candidates(record_id,body) VALUES (%s,%s)', (record_id,Jsonb(proposal)))
            state = 'proposed' if normalized else 'zero_output'
            conn.execute('''UPDATE compiler_runtime.operation_executions SET state=%s,generator_receipt=%s,
                updated_at=clock_timestamp() WHERE execution_id=%s''', (state,Jsonb(receipt),execution_id))
            self._event(conn,job,state)
        return {'execution_id':execution_id,'state':state,'proposal_count':len(proposals),'replayed':False}

    def decide(self, execution_id, decisions, receipt, *, checkpoint=None):
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn,execution_id,lock=True)
            self._receipt(receipt,'validator',job)
            if receipt.get('output_sha256') != digest({'decisions':decisions}):
                fail('provider_receipt_mismatch')
            if job['state'] in ('completed','needs_human'):
                if job['validator_receipt'] != receipt:
                    fail('validation_retry_conflict',6)
                return {'execution_id':execution_id,'state':job['state'],'replayed':True}
            if job['state'] != 'proposed':
                fail('job_not_ready',7)
            records = conn.execute('''SELECT r.*,c.body FROM compiler_runtime.records r
                JOIN compiler_runtime.temporary_candidates c USING(record_id)
                WHERE execution_id=%s ORDER BY ordinal''',(execution_id,)).fetchall()
            judged = validate_decisions(decisions,len(records))
            parsed = conn.execute('SELECT * FROM compiler_runtime.parse_artifacts WHERE execution_id=%s',(execution_id,)).fetchone()
            if (receipt.get('source_bundle_sha256') != digest(parsed['bundle'])
                    or receipt.get('proposal_set_sha256') != digest([r['body'] for r in records])):
                fail('provider_source_mismatch')
            blocks = {b['block_id']:b for b in parsed['bundle']['blocks']}
            source_mode = job['profile']['schema_version'] == SOURCE_PROFILE
            assemblies = None
            if source_mode:
                self._verify_source_artifacts(job, parsed)
                proposals = [r['body'] for r in records]
                algorithm = job['profile']['transformation']['algorithm']
                if algorithm in TEXT_ALGORITHMS:
                    checks, assemblies = text_assemblies(parsed['bundle'], proposals, algorithm)
                else:
                    checks = verify_units(parsed['bundle'], proposals, algorithm)
                if (decisions != self._source_decisions(proposals)
                        or receipt != self._source_receipt('validator', parsed['bundle'], proposals, checks)):
                    fail('invalid_source_receipt')
            coverage = ({'status':'complete'} if source_mode and job['profile']['transformation']['algorithm'] in TEXT_ALGORITHMS
                        else figure_coverage(parsed['bundle'], [r['body'] for r in records], decisions))
            results = []
            for record in records:
                decision = judged[record['ordinal']]
                # Retain reason codes, never rejected candidate prose in terminal records.
                codes = decision['reason_codes']
                if any(re.fullmatch(r'[a-z][a-z0-9_]{0,63}',code) is None for code in codes):
                    fail('invalid_reason_code')
                information_id = None
                proposal = validate_proposal(record['body'],blocks)
                if decision['verdict'] == 'accepted':
                    images = []
                    if proposal['image_block_id']:
                        images = [parsed['manifest']['files'][a['path']] for a in blocks[proposal['image_block_id']]['image_paths']]
                    payload = {'schema_version':'information-v1','images':images}
                    if source_mode:
                        payload.update({'schema_version':SOURCE_SCHEMA_VERSION,
                            'validation_basis':'source_structure', 'semantic_checked':False,
                            'empty_content':proposal['content']=='',
                            'source_blocks':[blocks[ref] for ref in proposal['block_ids']],
                            'source_bundle_sha256':digest(parsed['bundle']),
                            'parse_manifest_sha256':parsed['manifest_hash'],
                            'source_artifacts':{a['path']:parsed['manifest']['files'][a['path']]
                                for ref in proposal['block_ids'] for a in blocks[ref]['image_paths']},
                            'primary_block_id':proposal['image_block_id']})
                        payload.update(assemblies[tuple(proposal['block_ids'])] if assemblies is not None else
                            assembly_payload(parsed['bundle'], proposal, job['profile']['transformation']['algorithm']))
                    if proposal['image_block_id'] and blocks[proposal['image_block_id']].get('figure_id'):
                        figure = blocks[proposal['image_block_id']]
                        payload['figure'] = {key:figure[key] for key in (
                            'figure_id','figure_number','member_block_ids','caption_block_ids','figure_provenance')}
                    information_id = conn.execute('''INSERT INTO canonical_store.information
                        (data_id,origin_record_id,kind,semantic_type,title,content,payload,identity_fingerprint,content_fingerprint,unit_type)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING information_id''',
                        (job['data_id'],record['record_id'],proposal['kind'],proposal['semantic_type'],proposal['title'],proposal['content'],
                         Jsonb(payload),record['identity_fingerprint'],record['content_fingerprint'],proposal.get('unit_type'))).fetchone()['information_id']
                    for block_id in proposal['block_ids']:
                        block = blocks[block_id]
                        conn.execute('''INSERT INTO canonical_store.information_groundings
                            (information_id,data_id,parse_artifact_id,block_id,page_index,bbox,page_size,raw_locator,anchor_sha256,locator_type,text_range)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                            (information_id,job['data_id'],parsed['parse_artifact_id'],block_id,block['page_index'],
                             Jsonb(block['bbox']) if block['bbox'] is not None else None,
                             Jsonb(block['page_size']) if block['page_size'] is not None else None,
                             block['raw_locator'],block['anchor_sha256'],block.get('locator_type','pdf_region'),
                             Jsonb(block['text_range']) if 'text_range' in block else None))
                    conn.execute("INSERT INTO compiler_runtime.outbox(record_id,information_id,operation) VALUES (%s,%s,'i2k')", (record['record_id'],information_id))
                    results.append(information_id)
                conn.execute('''UPDATE compiler_runtime.records SET disposition=%s,reason_codes=%s,
                    result_information_id=%s,resolved_at=CASE WHEN %s='needs_human' THEN NULL ELSE clock_timestamp() END
                    WHERE record_id=%s''',
                    (decision['verdict'],Jsonb(codes),information_id,decision['verdict'],record['record_id']))
                if decision['verdict'] != 'needs_human':
                    conn.execute('DELETE FROM compiler_runtime.temporary_candidates WHERE record_id=%s', (record['record_id'],))
            if checkpoint:
                checkpoint('before_commit')
            state = 'needs_human' if (any(d['verdict']=='needs_human' for d in judged.values())
                                     or coverage['status']=='incomplete') else 'completed'
            conn.execute('''UPDATE compiler_runtime.operation_executions SET state=%s,validator_receipt=%s,
                updated_at=clock_timestamp() WHERE execution_id=%s''',(state,Jsonb(receipt),execution_id))
            self._event(conn,job,state)
        return {'execution_id':execution_id,'state':state,'information_ids':results,'replayed':False}

    @staticmethod
    def _source_decisions(proposals):
        return [{'ordinal':n, 'verdict':'accepted', 'reason_codes':['source_structure_verified'],
                 'reason':'Exact parser content and source coverage verified; no semantic assessment.'}
                for n in range(len(proposals))]

    def _verify_source_artifacts(self, job, parsed):
        if (parsed is None or digest(parsed['manifest']) != parsed['manifest_hash']
                or parsed['manifest']['bundle_sha256'] != digest(parsed['bundle'])):
            fail('parser_artifact_changed')
        if job['profile']['transformation']['algorithm'] in TEXT_ALGORITHMS:
            if (parsed['bundle']['data_id'] != job['data_id']
                    or parsed['manifest']['data_id'] != job['data_id']
                    or parsed['manifest']['profile'] != job['profile']['parser']
                    or parsed['bundle']['profile'] != job['profile']['parser']):
                fail('parser_artifact_changed')
            algorithm = job['profile']['transformation']['algorithm']
            verify_units(parsed['bundle'], build_units(parsed['bundle'], algorithm), algorithm)
        origin = job['profile']['policy'].get('source_reassembly')
        if parsed['manifest'].get('source_reassembly') != origin:
            fail('source_reassembly_mismatch')
        if origin is not None:
            with connection(self.dsn) as conn:
                parent = self._job(conn, origin['source_execution_id'])
                original = conn.execute('SELECT * FROM compiler_runtime.parse_artifacts WHERE execution_id=%s',
                                        (parent['execution_id'],)).fetchone()
            expected_manifest = ({**original['manifest'], 'source_reassembly': origin,
                                  'assembly_profile_sha256': digest(job['profile'])} if original else None)
            if (parent['state'] != 'completed' or parent['data_id'] != job['data_id']
                    or parent['profile']['schema_version'] != SOURCE_PROFILE
                    or parent['profile']['transformation']['algorithm'] != SOURCE_UNITS_VERSION
                    or digest(parent['profile']) != origin['source_profile_sha256']
                    or original is None or digest(original['manifest']) != origin['source_parse_manifest_sha256']
                    or original['manifest_hash'] != origin['source_parse_manifest_sha256']
                    or original['manifest']['bundle_sha256'] != digest(original['bundle'])
                    or original['bundle'] != parsed['bundle'] or expected_manifest != parsed['manifest']
                    or job['profile']['parser'] != parent['profile']['parser']):
                fail('source_reassembly_mismatch')
        page_origin = job['profile']['policy'].get('source_page_origin')
        if parsed['manifest'].get('source_page_origin') != page_origin:
            fail('source_page_mismatch')
        if page_origin is not None:
            from .source_pages import parent_bundle
            with connection(self.dsn) as conn:
                parent = self._job(conn, page_origin['source_execution_id'])
                original = conn.execute('SELECT * FROM compiler_runtime.parse_artifacts WHERE execution_id=%s',
                                        (parent['execution_id'],)).fetchone()
            if (parent['state'] != 'completed' or parent['data_id'] != job['data_id']
                    or parent['profile']['schema_version'] != SOURCE_PROFILE
                    or parent['profile']['transformation']['algorithm'] not in (SOURCE_UNITS_VERSION, SOURCE_GROUPS_VERSION, SOURCE_GROUPS_V2_VERSION)
                    or digest(parent['profile']) != page_origin['source_profile_sha256']
                    or original is None or original['manifest_hash'] != page_origin['source_parse_manifest_sha256']
                    or parent_bundle(parsed['bundle']) != original['bundle']
                    or parsed['bundle']['source_page_supplement']['evidence_manifest_sha256'] != page_origin['evidence_manifest_sha256']):
                fail('source_page_mismatch')
            self._verify_source_artifacts(parent, original)
            expected = deepcopy(original['manifest'])
            expected.pop('source_reassembly', None)
            for page in parsed['bundle']['source_page_supplement']['pages']:
                image = page['page_image']
                expected['files'][f"original_pages/page-{page['page_index']:04d}.png"] = {
                    'sha256': image['sha256'], 'byte_size': image['size_bytes'],
                    'artifact_path': f"derived/objects/sha256/{image['sha256'][:2]}/{image['sha256']}"}
            expected.update(source_page_origin=page_origin, assembly_profile_sha256=digest(job['profile']),
                            bundle_sha256=digest(parsed['bundle']))
            if expected != parsed['manifest'] or job['profile']['parser'] != parent['profile']['parser']:
                fail('source_page_mismatch')
        data = self.data.get_data(job['data_id'])
        if data is None:
            fail('data_not_found', 2)
        if (page_origin is not None and parsed['bundle']['source_page_supplement']['original_pdf_byte_size'] != data['byte_size']):
            fail('source_page_mismatch')
        self.store.verify(job['data_id'], data['byte_size'])
        for reference in parsed['manifest']['files'].values():
            self.derived.verify(reference['sha256'], reference['byte_size'])

    @staticmethod
    def _source_receipt(role, bundle, proposals, checks):
        output = {'proposals':proposals} if role == 'generator' else {
            'decisions':CompilerRuntime._source_decisions(proposals)}
        return {'receipt_kind':'deterministic_source_check', 'algorithm':checks['version'],
                'role':'source_builder' if role == 'generator' else 'source_checker',
                'llm_calls':0, 'source_bundle_sha256':digest(bundle),
                'proposal_set_sha256':digest(proposals), 'output_sha256':digest(output),
                'checks':checks}

    def materialize_source(self, execution_id, *, checkpoint=None):
        """Resume script-only D2I; completed executions reuse their immutable IDs."""
        job = self.show(execution_id, include_input=True)
        if job['profile']['schema_version'] != SOURCE_PROFILE:
            fail('source_profile_required', 2)
        if job['state'] == 'prepared' and job['profile']['transformation']['algorithm'] in TEXT_ALGORITHMS:
            self._attach_markdown(job)
            job = self.show(execution_id, include_input=True)
        if job['state'] in ('completed', 'zero_output'):
            result = {'execution_id':execution_id, 'state':job['state'],
                      'information_ids':job['information_ids'], 'replayed':True}
            if review := (job.get('validator_receipt') or {}).get('checks', {}).get('transcription_review'):
                result['transcription_review'] = review
            return result
        if job['state'] not in ('parsed', 'proposed'):
            fail('job_not_ready', 7)
        bundle = job['parse']['bundle']
        algorithm = job['profile']['transformation']['algorithm']
        proposals = build_units(bundle, algorithm)
        checks = verify_units(bundle, proposals, algorithm)
        if job['state'] == 'parsed':
            result = self.propose(execution_id, proposals,
                                 self._source_receipt('generator', bundle, proposals, checks))
            if result['state'] == 'zero_output':
                return result
        result = self.decide(execution_id, self._source_decisions(proposals),
                             self._source_receipt('validator', bundle, proposals, checks), checkpoint=checkpoint)
        if 'transcription_review' in checks:
            result['transcription_review'] = checks['transcription_review']
        return result

    def regroup_source(self, execution_id, *, checkpoint=None):
        """Create grouped I from a verified completed source, retaining its parser history."""
        source, parsed, _ = self._source_snapshot(execution_id)
        if source['profile']['transformation']['algorithm'] in (SOURCE_GROUPS_VERSION, SOURCE_GROUPS_V2_VERSION, SOURCE_PAGE_GROUPS_VERSION, *TEXT_ALGORITHMS):
            return self.materialize_source(execution_id)
        profile = deepcopy(source['profile'])
        profile['transformation']['algorithm'] = SOURCE_GROUPS_V2_VERSION
        implementations = profile['policy'].setdefault('implementation_sha256', {})
        for name in ('source_groups.py', 'section_projection.py', 'figure_references.py', 'source_units.py',
                     'information.py', 'd2i.py', 'compiler_runtime.py'):
            implementations['src/palimpsest/' + name] = sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        origin = {'source_execution_id': str(source['execution_id']),
                  'source_profile_sha256': digest(source['profile']),
                  'source_parse_manifest_sha256': parsed['manifest_hash']}
        profile['policy']['source_reassembly'] = origin
        target = self.start(source['data_id'], profile)
        target_id = str(target['execution_id'])
        manifest = {**deepcopy(parsed['manifest']), 'source_reassembly': origin,
                    'assembly_profile_sha256': digest(profile)}
        with tempfile.TemporaryDirectory(prefix='palim-regroup-') as temporary:
            path = Path(temporary) / 'manifest.json'
            path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding='utf-8')
            published = self._publish(path)
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn, target_id, lock=True)
            existing = conn.execute('SELECT * FROM compiler_runtime.parse_artifacts WHERE execution_id=%s',
                                    (target_id,)).fetchone()
            if existing:
                if existing['manifest_hash'] != digest(manifest) or existing['bundle'] != parsed['bundle']:
                    fail('parser_retry_conflict', 6)
            else:
                if job['state'] != 'prepared':
                    fail('job_not_ready', 7)
                conn.execute('''INSERT INTO compiler_runtime.parse_artifacts
                    (execution_id,data_id,manifest_hash,artifact_path,manifest,bundle) VALUES (%s,%s,%s,%s,%s,%s)''',
                    (target_id,job['data_id'],digest(manifest),published['artifact_path'],Jsonb(manifest),Jsonb(parsed['bundle'])))
                conn.execute("UPDATE compiler_runtime.operation_executions SET state='parsed',updated_at=clock_timestamp() WHERE execution_id=%s", (target_id,))
                self._event(conn,job,'parsed')
        result = self.materialize_source(target_id, checkpoint=checkpoint)
        if result['state'] == 'completed' and 'information_ids' not in result:
            result['information_ids'] = self.show(target_id)['information_ids']
        result.update(source_execution_id=str(source['execution_id']), new_parser_calls=0,
                      source_algorithm=SOURCE_GROUPS_V2_VERSION)
        return result

    def add_source_pages(self, execution_id, directory, *, checkpoint=None):
        """Publish a new source execution with actual original-page Image I."""
        from .pdf_evidence import read_evidence, local_file
        from .source_pages import add_page_blocks
        source, parsed, _ = self._source_snapshot(execution_id)
        if source['profile']['transformation']['algorithm'] == SOURCE_PAGE_GROUPS_VERSION:
            return self.materialize_source(execution_id)
        if source['profile']['transformation']['algorithm'] not in (SOURCE_UNITS_VERSION, SOURCE_GROUPS_VERSION, SOURCE_GROUPS_V2_VERSION):
            fail('pdf_source_required', 2)
        evidence = read_evidence(directory)
        if (evidence['source_bundle'] != parsed['bundle']
                or evidence['visuals']['source']['pdf_size_bytes'] != self.data.get_data(source['data_id'])['byte_size']):
            fail('source_page_mismatch')
        bundle = add_page_blocks(parsed['bundle'], evidence['visuals'],
                                 evidence_manifest_sha256=evidence['manifest_sha256'])
        profile = deepcopy(source['profile'])
        profile['transformation']['algorithm'] = SOURCE_PAGE_GROUPS_VERSION
        profile['policy'].pop('source_reassembly', None)
        origin = {'source_execution_id': str(source['execution_id']),
                  'source_profile_sha256': digest(source['profile']),
                  'source_parse_manifest_sha256': parsed['manifest_hash'],
                  'evidence_manifest_sha256': evidence['manifest_sha256']}
        profile['policy']['source_page_origin'] = origin
        for name in ('source_pages.py','d2i.py','i2k.py','compiler_runtime.py'):
            profile['policy'].setdefault('implementation_sha256', {})['src/palimpsest/'+name] = sha256(
                Path(__file__).with_name(name).read_bytes()).hexdigest()
        target = self.start(source['data_id'], profile)
        manifest = deepcopy(parsed['manifest'])
        manifest.pop('source_reassembly', None)
        for page in evidence['visuals']['pages']:
            image = page['page_image']
            published = self._publish(local_file(Path(evidence['asset_base_directory']), image['path']))
            if published['sha256'] != image['sha256'] or published['byte_size'] != image['size_bytes']:
                fail('source_page_mismatch')
            png = self.derived.read(published['sha256'], published['byte_size'])
            if (png[:8] != b'\x89PNG\r\n\x1a\n' or png[12:16] != b'IHDR'
                    or [int.from_bytes(png[16:20],'big'),int.from_bytes(png[20:24],'big')] != image['pixel_size']):
                fail('source_page_mismatch')
            manifest['files'][f"original_pages/page-{page['page_index']:04d}.png"] = published
        manifest.update(source_page_origin=origin, assembly_profile_sha256=digest(profile),
                        bundle_sha256=digest(bundle))
        target_id = str(target['execution_id'])
        self._save_parse(target_id, bundle, manifest)
        result = self.materialize_source(target_id, checkpoint=checkpoint)
        if result['state'] == 'completed' and 'information_ids' not in result:
            result['information_ids'] = self.show(target_id)['information_ids']
        return {**result, 'source_execution_id': str(execution_id), 'source_algorithm': SOURCE_PAGE_GROUPS_VERSION,
                'page_image_information_count': len(bundle['pages']), 'parser_calls': 0, 'llm_calls': 0}

    def mark_failed(self, execution_id, code):
        if not isinstance(code,str) or re.fullmatch(r'[a-z][a-z0-9_]{0,63}',code) is None:
            fail('invalid_error_code',2)
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn,execution_id,lock=True)
            if job['state'] not in ('completed','zero_output','needs_human','failed'):
                conn.execute("UPDATE compiler_runtime.operation_executions SET state='failed',error_code=%s,updated_at=clock_timestamp() WHERE execution_id=%s", (code,execution_id))
                self._event(conn,job,'failed',code)
        return self.show(execution_id)

    def retry(self, execution_id):
        with connection(self.dsn) as conn, conn.transaction():
            job = self._job(conn,execution_id,lock=True)
            if job['state'] == 'failed':
                parsed = conn.execute('SELECT 1 FROM compiler_runtime.parse_artifacts WHERE execution_id=%s',(execution_id,)).fetchone()
                state = 'proposed' if job['generator_receipt'] else ('parsed' if parsed else 'prepared')
                job = conn.execute('''UPDATE compiler_runtime.operation_executions SET state=%s,error_code=NULL,
                    attempt=attempt+1,updated_at=clock_timestamp() WHERE execution_id=%s RETURNING *''',(state,execution_id)).fetchone()
                self._event(conn,job,state)
        return self.show(execution_id)

    def information(self, *, information_id=None, data_id=None):
        with connection(self.dsn) as conn:
            if information_id:
                rows = conn.execute('SELECT * FROM canonical_store.information WHERE information_id=%s',(request_id(str(information_id)),)).fetchall()
            else:
                rows = conn.execute('SELECT * FROM canonical_store.information WHERE data_id=%s ORDER BY information_id',(validate_data_id(data_id),)).fetchall()
            for row in rows:
                row['groundings'] = conn.execute('''SELECT * FROM canonical_store.information_groundings
                    WHERE information_id=%s ORDER BY grounding_id''',(row['information_id'],)).fetchall()
            return {'information':rows}

    def section_view(self, execution_id, directory, *, section_id=None, expected_projection_sha256=None, whole_document=False):
        """Bind a reading projection to one verified completed source execution."""
        from .pdf_evidence import read_evidence
        from .section_projection import build_sections, section_context, document_context

        pages = self.page_view(execution_id)
        evidence = read_evidence(directory)
        if whole_document:
            if section_id is not None:
                fail('invalid_arguments', 2)
            return document_context(evidence, canonical_pages=pages,
                                    expected_projection_sha256=expected_projection_sha256)
        return (build_sections(evidence, canonical_pages=pages) if section_id is None
                else section_context(evidence, section_id, canonical_pages=pages,
                                     expected_projection_sha256=expected_projection_sha256))

    def _source_snapshot(self, execution_id):
        """Read immutable I from one completed source execution and verify its files."""
        with connection(self.dsn) as conn:
            job = self._job(conn, execution_id)
            if job['profile']['schema_version'] != SOURCE_PROFILE or job['state'] != 'completed':
                fail('completed_source_execution_required', 2)
            parsed = conn.execute('SELECT * FROM compiler_runtime.parse_artifacts WHERE execution_id=%s',
                                  (execution_id,)).fetchone()
            rows = conn.execute('''SELECT i.* FROM canonical_store.information i
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
                WHERE r.execution_id=%s ORDER BY r.ordinal''', (execution_id,)).fetchall()
        self._verify_source_artifacts(job, parsed)
        return job, parsed, rows

    def prepare_input(self, execution_id, *, information_ids=None, directory=None,
                      section_id=None, expected_projection_sha256=None):
        """Prepare an I-only payload; neither provider delivery nor K acceptance."""
        from .i2k import build_input
        from .page_projection import build_pages
        from .pdf_evidence import read_evidence
        from .section_projection import section_context

        if (section_id is None) != (expected_projection_sha256 is None):
            fail('section_projection_required', 2)
        if section_id is not None and (directory is None or information_ids is not None):
            fail('invalid_input_selection', 2)
        job, parsed, rows = self._source_snapshot(execution_id)
        markdown = job['profile']['transformation']['algorithm'] in TEXT_ALGORITHMS
        if markdown and (directory is not None or section_id is not None):
            fail('pdf_evidence_view_required', 2)
        with connection(self.dsn) as conn:
            groundings = conn.execute('''SELECT g.* FROM canonical_store.information_groundings g
                JOIN canonical_store.information i USING(information_id)
                JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
                WHERE r.execution_id=%s ORDER BY g.grounding_id''', (execution_id,)).fetchall()
        by_information = {}
        for grounding in groundings:
            if (grounding['data_id'] != job['data_id']
                    or grounding['parse_artifact_id'] != parsed['parse_artifact_id']):
                fail('input_grounding_mismatch')
            by_information.setdefault(str(grounding['information_id']), []).append(grounding)
        keys = ('block_id', 'page_index', 'bbox', 'page_size', 'raw_locator', 'anchor_sha256')
        if markdown:
            keys += ('locator_type', 'text_range')
        for row in rows:
            if row.get('payload', {}).get('schema_version') != SOURCE_SCHEMA_VERSION:
                fail('invalid_information_snapshot')
            row['groundings'] = by_information.get(str(row['information_id']), [])
            expected = {b['block_id']: {k:b[k] for k in keys} for b in row['payload']['source_blocks']}
            actual = {g['block_id']: {k:g[k] for k in keys} for g in row['groundings']}
            if (len(actual) != len(row['groundings']) or actual != expected
                    or row['payload']['parse_manifest_sha256'] != parsed['manifest_hash']):
                fail('input_grounding_mismatch')
            assets = {a['path']: parsed['manifest']['files'].get(a['path'])
                      for block in row['payload']['source_blocks'] for a in block['image_paths']}
            if any(asset is None for asset in assets.values()) or row['payload'].get('source_artifacts') != assets:
                fail('input_media_mismatch')
        evidence = read_evidence(directory) if directory is not None else None
        context_ids = None
        if section_id is not None:
            pages = build_pages(parsed['bundle'], rows)
            pages.update(execution_id=str(job['execution_id']), profile_id=str(job['profile_id']))
            pages['projection_sha256'] = digest({k:v for k,v in pages.items() if k != 'projection_sha256'})
            selected = section_context(evidence, section_id, canonical_pages=pages,
                                       expected_projection_sha256=expected_projection_sha256)
            mapping = selected['source_information_ids']
            information_ids = list(dict.fromkeys(mapping[ref] for ref in selected['target_source_block_ids']))
            context_ids = list(dict.fromkeys(mapping[ref] for ref in selected['context_source_block_ids']))
        return build_input(parsed['bundle'], rows, execution_id=str(job['execution_id']),
                           profile_id=str(job['profile_id']), selected_information_ids=information_ids,
                           context_information_ids=context_ids, evidence=evidence,
                           assembly_algorithm=job['profile']['transformation']['algorithm'])

    def prepare_source(self, execution_id, request, **selection):
        """Validate a source request and read the registered original PDF locally."""
        from .i2k import validate_source_request

        packet = self.prepare_input(execution_id, **selection)
        validated = validate_source_request(request, packet)
        data = self.data.get_data(packet['data_id'])
        if data is None or data['media_type'] != 'application/pdf':
            fail('original_pdf_required', 2)
        relative = f"objects/sha256/{packet['data_id'][:2]}/{packet['data_id']}"
        if data['artifact_path'] != relative:
            fail('original_pdf_path_mismatch')
        content = self.store.read(packet['data_id'], data['byte_size'])
        if b'%PDF-' not in content[:1024]:
            fail('original_pdf_required', 2)
        result = {'schema_version':'i2k-source-preparation-v1', 'data_id':packet['data_id'],
                  'source_execution_id':str(execution_id), 'input_sha256':packet['input_sha256'],
                  'request':validated, 'request_sha256':validated['request_sha256'],
                  'original_pdf':{'sha256':packet['data_id'], 'byte_size':len(content),
                                  'artifact_path':relative, 'media_type':'application/pdf'},
                  'preparation_status':'prepared', 'delivery_status':'not_delivered',
                  'request_validation':'structural_only', 'actual_citations':[],
                  'llm_calls':0, 'canonical_writes':0}
        result['preparation_sha256'] = digest(result)
        return result

    def reconstruct_source(self, execution_id):
        """Reassemble this execution's exact I blocks; do not mix historical I."""
        from .source_reconstruction import build_reconstruction
        packet = self.prepare_input(execution_id)
        _, parsed, rows = self._source_snapshot(execution_id)
        return build_reconstruction(parsed['bundle'], rows, packet, self.data.get_data(packet['data_id']))

    def lookup_source(self, execution_id, **location):
        from .source_reconstruction import lookup_source
        return lookup_source(self.prepare_input(execution_id), **location)

    def locate_information(self, execution_id, information_id, *, char_range=None):
        from .source_reconstruction import locate_information
        return locate_information(self.prepare_input(execution_id), information_id, char_range=char_range)

    def export_source(self, execution_id, destination):
        """Copy registered original bytes atomically, without replacing a file."""
        packet = self.prepare_input(execution_id)
        data = self.data.get_data(packet['data_id'])
        expected_path = f"objects/sha256/{packet['data_id'][:2]}/{packet['data_id']}"
        if data is None or data['artifact_path'] != expected_path:
            fail('original_source_path_mismatch')
        content = self.store.read(packet['data_id'], data['byte_size'])
        destination = Path(destination)
        if '..' in destination.parts:
            fail('unsafe_export_path')
        destination = destination.absolute()
        temporary = '.palim-export-' + os.urandom(16).hex()
        replayed = False
        with self.store._io_errors(), _directory(destination.parent, create=True) as parent:
            try:
                with _file(parent, temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL) as descriptor:
                    remaining = memoryview(content)
                    while remaining:
                        count = os.write(descriptor, remaining)
                        if not count:
                            raise OSError('Original export write made no progress')
                        remaining = remaining[count:]
                    os.fsync(descriptor)
                    saved = _read_payload(descriptor, parent, temporary)
                    if saved.data_id != packet['data_id'] or saved.byte_size != len(content):
                        fail('integrity_conflict', 6)
                    try:
                        os.link(temporary, destination.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                    except FileExistsError:
                        replayed = True
                    with _file(parent, destination.name) as exported:
                        if _read_payload(exported, parent, destination.name) != saved:
                            fail('export_conflict', 6)
                    os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                    os.fsync(parent)
                except FileNotFoundError:
                    pass
        result = {'schema_version':'source-export-v1','source_execution_id':str(execution_id),
            'data_id':packet['data_id'],'input_sha256':packet['input_sha256'],
            'original_artifact_path':expected_path,'destination':str(destination),
            'sha256':packet['data_id'],'byte_size':len(content),'media_type':data['media_type'],
            'byte_identical':True,'replayed':replayed,'source':'registered_original_artifact',
            'llm_calls':0,'canonical_writes':0}
        result['export_sha256'] = digest(result)
        return result

    def page_view(self, execution_id, *, page_number=None):
        """Project one completed source execution; never mix historical runs."""
        from .page_projection import build_pages, select_page_context

        job, parsed, rows = self._source_snapshot(execution_id)
        projection = build_pages(parsed['bundle'], rows)
        metadata = {'execution_id':str(job['execution_id']), 'profile_id':str(job['profile_id'])}
        projection.update(metadata)
        projection['projection_sha256'] = digest({k:v for k,v in projection.items() if k!='projection_sha256'})
        if page_number is None:
            return projection
        result = select_page_context(projection, page_number)
        result.update(metadata)
        result['context_sha256'] = digest({k:v for k,v in result.items() if k!='context_sha256'})
        return result
