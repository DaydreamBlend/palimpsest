"""Native code D2I integration in the explicit disposable Linux PostgreSQL DB.

Each case registers unique fixture bytes in its own temporary Artifact Store.
No migration, history deletion, original user dataset or model is used here.
"""

from copy import deepcopy
from hashlib import sha256
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from palimpsest import code_snapshot, knowledge_prompts, multi_source_prompts
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import PostgresRepository, connection
from palimpsest.code_adapter import CODE_ALGORITHM, CODE_PARSER, CODE_SCHEMA
from palimpsest.compiler_runtime import CompilerRuntime, digest
from palimpsest.errors import PalimpsestError
from palimpsest.multi_source_i2k import combine_packets
from palimpsest.service import DataService
from palimpsest.source_review import build_manifest


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires the explicit Linux PostgreSQL fixture database palimpsest')
class CodeRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ['PALIMPSEST_TEST_DSN']
        with connection(cls.dsn) as conn:
            if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'palimpsest':
                raise RuntimeError('Code integration requires the isolated database named palimpsest')
            if int(conn.execute('SHOW server_version_num').fetchone()['server_version_num']) // 10000 != 18:
                raise RuntimeError('Code integration requires PostgreSQL 18')
            if not conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone():
                raise RuntimeError('Provision pgvector before code integration tests')
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations "
                                "WHERE version='0004_text_groundings'").fetchone():
                raise RuntimeError('Provision the reviewed text-grounding migration first')

    def setUp(self):
        temporary = TemporaryDirectory(prefix='native-code-runtime-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.code = self.base / 'repository'
        (self.code / 'src').mkdir(parents=True)
        padding = 'x' * 3300
        self.members = {
            'src/example.py': (f'\ufeff# Unique fixture {uuid4()}\r\nimport os\r\nCONFIG = 7\r\n\r\n'
                'def literal():\r\n    return "μ 😀 Cafe\u0301"\r\n\r\n'
                'class Large:\r\n    """Retained class context."""\r\n    SETTING = 3\r\n'
                f'    @decorator\r\n    def first(self):\r\n        return "{padding}"\r\n\r\n'
                f'    async def second(self):\r\n        return "{padding}"\r\n# exact final comment\r\n'),
            'src/broken.py': 'def retained(): return 1\n\ndef broken(:\n    pass\n',
            'src/empty.py': '',
            'README.md': '# Retained opaque member\n\nCode is source data, not an executed result.\n',
        }
        for name, content in self.members.items():
            (self.code / name).write_bytes(content.encode('utf-8'))
        self.directory = self.code / 'snapshot'
        self.manifest = code_snapshot.snapshot(self.code, self.directory, paths=list(self.members))
        self.raw = (self.directory / 'dossier.md').read_bytes()
        self.data_id = sha256(self.raw).hexdigest()
        self.root = self.base / 'artifacts'
        self.repository = PostgresRepository(self.dsn)
        self.store = ArtifactStore(self.root)
        self.service = DataService(self.repository, self.store, actor_ref='local')
        self.runtime = CompilerRuntime(self.dsn, self.root)

    def row(self, query, parameters=()):
        with connection(self.dsn) as conn:
            return conn.execute(query, parameters).fetchone()

    def counts(self, data_id=None):
        return self.row('''SELECT
            (SELECT count(*) FROM canonical_store.data WHERE data_id=%s) AS data,
            (SELECT count(*) FROM canonical_store.data_acquisitions WHERE data_id=%s) AS acquisitions,
            (SELECT count(*) FROM canonical_store.information WHERE data_id=%s) AS information,
            (SELECT count(*) FROM compiler_runtime.operation_executions WHERE data_id=%s AND operation='d2i') AS d2i''',
            (data_id or self.data_id,) * 4)

    def compile(self):
        self.service.import_code_snapshot(self.directory)
        return self.runtime.compile_code(self.data_id)

    def assert_error(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)

    def test_native_compilation_persists_exact_source_context_and_every_member(self):
        registered = self.service.import_code_snapshot(self.directory)
        result = self.runtime.compile_code(self.data_id)
        execution = result['execution_id']
        self.assertEqual((result['state'], result['source_algorithm'], result['llm_calls'], result['ocr_calls']),
                         ('completed', CODE_ALGORITHM, 0, 0))
        self.assertEqual(registered['data_id'], self.data_id)
        self.assertEqual(self.store.storage_stats(self.data_id, len(self.raw))['storage'], 'segmented-v1')
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)
        self.assertEqual(self.service.show(self.data_id)['media_type'], 'text/markdown')
        self.assertFalse((self.root / f'objects/sha256/{self.data_id[:2]}/{self.data_id}').exists())
        job = self.runtime.show(execution, include_input=True)
        self.assertEqual(job['profile']['parser'], CODE_PARSER)
        self.assertEqual(job['parse']['bundle']['schema_version'], CODE_SCHEMA)
        self.assertEqual([event['state'] for event in job['events']], ['prepared', 'parsed', 'proposed', 'completed'])
        for role in ('generator', 'validator'):
            receipt = job[role + '_receipt']
            self.assertEqual(receipt['receipt_kind'], 'deterministic_source_check')
            self.assertEqual((receipt['checks']['version'], receipt['llm_calls']), (CODE_ALGORITHM, 0))
        packet = self.runtime.prepare_input(execution)
        units = packet['model_input']['information']
        self.assertEqual(packet['model_input']['source_format'], 'code')
        self.assertFalse(packet['model_input']['original_pdf_request_supported'])
        self.assertEqual((packet['state'], packet['actual_delivery'], packet['page_count']),
                         ('prepared_not_delivered', False, 0))
        self.assertEqual(packet['media_assets'], [])
        self.assertEqual(''.join(unit['content'] for unit in units).encode('utf-8'), self.raw)
        rows = {str(row['information_id']): row for row in self.runtime.information(data_id=self.data_id)['information']}
        self.assertEqual(set(rows), set(packet['target_information_ids']))
        for unit in units:
            row = rows[unit['information_id']]
            self.assertEqual(UUID(unit['information_id']).version, 7)
            self.assertEqual((row['kind'], row['unit_type'], row['semantic_type']), ('text', 'text', None))
            self.assertFalse(row['payload']['semantic_checked'])
            self.assertEqual(row['payload']['source_bundle_sha256'], digest(job['parse']['bundle']))
            block, = row['payload']['source_blocks']
            grounding, = row['groundings']
            reference, = unit['source_refs']
            segment, = unit['source_assembly']['content_segments']
            self.assertEqual(unit['code_context'], [block['code_context']])
            self.assertEqual(reference['code_context'], block['code_context'])
            self.assertEqual(segment['code_context'], block['code_context'])
            self.assertEqual(grounding['text_range'], block['text_range'])
            self.assertEqual(grounding['locator_type'], 'text_range')
            self.assertEqual(grounding['parse_artifact_id'], job['parse']['parse_artifact_id'])
            self.assertEqual(reference['grounding_id'], str(grounding['grounding_id']))
            span = grounding['text_range']
            self.assertEqual(self.raw[span['byte_start']:span['byte_end']], row['content'].encode('utf-8'))
            self.assertTrue(all(grounding[key] is None for key in ('page_index', 'bbox', 'page_size')))
        for name, expected in self.members.items():
            selected = [unit for unit in units if unit['code_context'][0].get('member_path') == name]
            self.assertTrue(selected)
            self.assertEqual(''.join(unit['content'] for unit in selected), expected)
            status = 'syntax_error' if name.endswith('broken.py') else 'not_python' if name.endswith('.md') else 'parsed'
            self.assertTrue(all(unit['code_context'][0]['parse_status'] == status for unit in selected))
            self.assertTrue(all(unit['code_context'][0]['member_sha256'] == sha256(expected.encode('utf-8')).hexdigest()
                                for unit in selected))
        review = build_manifest(packet)
        self.assertEqual(len(review['targets']), len(units))
        self.assertNotIn('unmapped', {target['mapping_status'] for target in review['targets']})
        for projected in (knowledge_prompts.source_input(packet, []),
                          multi_source_prompts.source_input(combine_packets([packet]), [])):
            self.assertEqual([unit['code_context'] for unit in projected['information']],
                             [unit['code_context'] for unit in units])
        self.assertEqual(self.counts(), {'data': 1, 'acquisitions': 1, 'information': len(units), 'd2i': 1})
        self.assert_error('pdf_page_view_required', lambda: self.runtime.page_view(execution))

    def test_reconstruction_and_unicode_lookup_resolve_exact_D_and_member_spans(self):
        execution = self.compile()['execution_id']
        packet = self.runtime.prepare_input(execution)
        reconstruction = self.runtime.reconstruct_source(execution)
        self.assertTrue(reconstruction['exact_retained_block_coverage'])
        self.assertEqual(reconstruction['source_coverage'], 'exact_utf8_source_bytes')
        self.assertEqual(''.join(block['text'] for block in reconstruction['retained_blocks']).encode('utf-8'), self.raw)
        self.assertEqual((reconstruction['llm_calls'], reconstruction['canonical_writes']), (0, 0))
        needle = 'μ 😀 Cafe\u0301'
        unit = next(unit for unit in packet['model_input']['information']
                    if unit['code_context'][0].get('member_path') == 'src/example.py' and needle in unit['content'])
        begin = unit['content'].index(needle)
        located = self.runtime.locate_information(execution, unit['information_id'], char_range=[begin, begin + len(needle)])
        segment, = located['content_segments']
        byte_range = segment['matched_source_byte_range']
        self.assertEqual(self.raw[byte_range[0]:byte_range[1]], needle.encode('utf-8'))
        mapped = code_snapshot.locate(self.directory, byte_range=byte_range)
        match, = mapped['matches']
        self.assertEqual(match['path'], 'src/example.py')
        self.assertEqual(match['sha256'], sha256(self.members['src/example.py'].encode('utf-8')).hexdigest())
        self.assertEqual(mapped['unmapped_ranges'], [])
        self.assertEqual(segment['matched_member_char_range'], match['source_char_range'])
        self.assertEqual(segment['matched_member_byte_range'], match['source_byte_range'])
        self.assertEqual(segment['matched_member_line_range'], match['line_range'])
        source = self.members['src/example.py']
        a, b = match['source_char_range']
        self.assertEqual(source[a:b], needle)
        looked_up = self.runtime.lookup_source(execution, byte_range=byte_range)
        self.assertEqual(looked_up['parsed_information_ids'], [unit['information_id']])
        self.assertEqual(looked_up['matches'][0]['source_refs'][0]['code_context'], unit['code_context'][0])
        global_line = unit['source_refs'][0]['text_range']['line_start']
        self.assertIn(unit['information_id'], self.runtime.lookup_source(execution, line_range=[global_line, global_line])['parsed_information_ids'])
        first = next(unit for unit in packet['model_input']['information']
                     if unit['code_context'][0].get('member_path') == 'src/example.py'
                     and unit['code_context'][0]['member_text_range']['char_start'] == 0)
        bom = self.runtime.locate_information(execution, first['information_id'], char_range=[0, 1])['content_segments'][0]
        bom_match, = code_snapshot.locate(self.directory, byte_range=bom['matched_source_byte_range'])['matches']
        self.assertEqual(bom['matched_member_char_range'], bom_match['source_char_range'])
        self.assertEqual(bom['matched_member_byte_range'], bom_match['source_byte_range'])
        self.assertEqual(bom['matched_member_line_range'], bom_match['line_range'])
        self.assertEqual((bom['matched_member_char_range'], bom['matched_member_byte_range'], bom['matched_member_line_range']),
                         ([0, 1], [0, 3], [1, 1]))
        wrapper = next(unit for unit in packet['model_input']['information']
                       if unit['code_context'][0]['representation_role'] == 'dossier_metadata')
        wrapper_segment, = self.runtime.locate_information(execution, wrapper['information_id'], char_range=[0, 1])['content_segments']
        self.assertNotIn('matched_member_byte_range', wrapper_segment)
        destination = self.base / 'restored-dossier.md'
        exported = self.runtime.export_source(execution, destination)
        self.assertTrue(exported['byte_identical'])
        self.assertEqual(destination.read_bytes(), self.raw)

    def test_explicit_native_profile_preserves_old_markdown_history_and_replays_ids(self):
        registered = self.service.import_code_snapshot(self.directory)
        old = self.runtime.compile_markdown(self.data_id)
        old_job = deepcopy(self.runtime.show(old['execution_id'], include_input=True))
        old_packet = deepcopy(self.runtime.prepare_input(old['execution_id']))
        old_rows = deepcopy(self.runtime.information(data_id=self.data_id)['information'])
        native = self.runtime.compile_code(self.data_id)
        self.assertNotEqual(native['execution_id'], old['execution_id'])
        self.assertFalse(set(map(str, old['information_ids'])) & set(map(str, native['information_ids'])))
        self.assertGreater(len(native['information_ids']), len(old['information_ids']))
        self.assertEqual(self.runtime.show(old['execution_id'], include_input=True), old_job)
        self.assertEqual(self.runtime.prepare_input(old['execution_id']), old_packet)
        for old_row in old_rows:
            current, = self.runtime.information(information_id=old_row['information_id'])['information']
            self.assertEqual(current, old_row)
        counts = self.counts()
        self.assertEqual(counts['d2i'], 2)
        self.assertEqual(counts['information'], len(old['information_ids']) + len(native['information_ids']))
        for compile_method, expected in ((self.runtime.compile_markdown, old), (self.runtime.compile_code, native)):
            replay = compile_method(self.data_id)
            self.assertTrue(replay['replayed'])
            self.assertEqual(replay['execution_id'], expected['execution_id'])
            self.assertEqual(replay['information_ids'], expected['information_ids'])
        self.assertTrue(self.service.import_code_snapshot(self.directory, request_id=registered['request_id'])['replayed'])
        self.assertEqual(self.counts(), counts)
        self.assertEqual(self.store.read(self.data_id, len(self.raw)), self.raw)

    def test_changed_profile_and_canonical_context_are_rejected_without_history_writes(self):
        result = self.compile()
        execution = result['execution_id']
        job = self.runtime.show(execution, include_input=True)
        packet = self.runtime.prepare_input(execution)
        counts = self.counts()
        for field in ('version', 'target_characters', 'algorithm'):
            profile = deepcopy(job['profile'])
            if field == 'algorithm':
                profile['transformation']['algorithm'] = 'markdown-groups-v1'
            elif field == 'version':
                profile['parser']['version'] = 'unrecorded-version'
            else:
                profile['parser']['target_characters'] += 1
            self.assert_error('invalid_compilation_profile', lambda: self.runtime.start(self.data_id, profile))
        snapshot = self.runtime._source_snapshot(execution)
        changed = deepcopy(snapshot)
        changed[2][0]['payload']['source_blocks'][0]['code_context']['representation_role'] = 'invented'
        with patch.object(self.runtime, '_source_snapshot', return_value=changed):
            self.assert_error('invalid_i2k_input', lambda: self.runtime.prepare_input(execution))
        parsed = deepcopy(job['parse'])
        parsed['bundle']['profile']['version'] = 'invented'
        self.assert_error('parser_artifact_changed', lambda: self.runtime._verify_source_artifacts(job, parsed))
        self.assertEqual(self.runtime.prepare_input(execution), packet)
        self.assertEqual(self.runtime.show(execution, include_input=True), job)
        self.assertEqual(self.counts(), counts)

    def test_plain_markdown_is_not_silently_accepted_as_code_and_failure_is_retained(self):
        source = self.base / 'ordinary.md'
        raw = f'# Ordinary Markdown {uuid4()}\n\ndef source_is_not_a_dossier(): pass\n'.encode('utf-8')
        source.write_bytes(raw)
        registered = self.service.import_file(source, media_type='text/markdown')
        identifier = registered['data_id']
        self.assert_error('invalid_code_source', lambda: self.runtime.compile_code(identifier))
        job = self.row("SELECT execution_id,state,error_code FROM compiler_runtime.operation_executions "
                       "WHERE data_id=%s AND operation='d2i'", (identifier,))
        self.assertEqual((job['state'], job['error_code']), ('failed', 'invalid_code_source'))
        self.assertEqual(self.counts(identifier), {'data': 1, 'acquisitions': 1, 'information': 0, 'd2i': 1})
        self.assertEqual(self.store.read(identifier, len(raw)), raw)
        self.assertEqual(self.runtime.show(job['execution_id'])['events'][-1]['state'], 'failed')


if __name__ == '__main__':
    unittest.main()
