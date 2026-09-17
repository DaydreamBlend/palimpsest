"""Source-only catalog and bridge contracts; mocked SQL, no live DB or model."""

from base64 import b64decode
from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from palimpsest import desktop_read, source_read
from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import MIGRATIONS, migration_source
from palimpsest.compiler_runtime import SOURCE_PROFILE
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from test_multi_source_i2k import packet, uid


class FakeConnection:
    def __init__(self, version=6):
        self.version, self.read_only = version, 'on'
        self.installed = [{'version': name, 'checksum': migration_source(name)[1]} for name in MIGRATIONS[:version]]
        self.calls = []
        self.packet = packet(1)
        self.packet['actual_delivery'] = False
        self.packet['input_sha256'] = digest({key: value for key, value in self.packet.items() if key != 'input_sha256'})
        unit = self.packet['model_input']['information'][0]
        self.owner = self.packet['data_id']
        self.data = [{'data_id': self.owner, 'media_type': 'application/pdf', 'byte_size': 18,
            'filename': 'Existing paper.pdf', 'created_at': '2026-09-14T00:00:00Z'},
            {'data_id': '2' * 64, 'media_type': 'text/html; charset=UTF-8', 'byte_size': 40,
             'filename': 'Saved web snapshot.html', 'created_at': '2026-09-14T01:00:00Z'}]
        self.executions = [{'execution_id': self.packet['source_execution_id'], 'data_id': self.owner,
            'operation': 'd2i', 'state': 'completed', 'profile_id': self.packet['profile_id'],
            'profile_hash': 'f' * 64, 'profile': {'schema_version': SOURCE_PROFILE,
                'transformation': {'algorithm': 'source-units-v1'}},
            'generation': 1, 'attempt': 1, 'error_code': None, 'created_at': '2026-09-14T00:00:00Z',
            'updated_at': '2026-09-14T00:00:00Z', 'information_count': 1}]
        self.units = [{**deepcopy(unit), 'data_id': self.owner, 'source_execution_id': self.packet['source_execution_id'],
            'disposition': 'accepted', 'result_information_id': unit['information_id'],
            'semantic_type': None, 'payload': {'schema_version': 'source-information-v1'}, 'ordinal': 0}]
        self.acquisitions = [{'acquisition_id': uid(800), 'data_id': '2' * 64,
            'origin_uri': 'https://example.invalid/saved', 'import_method': 'capture',
            'original_name': 'snapshot.html', 'created_at': '2026-09-14T01:00:00Z', 'retrieved_at': None}]
        self.versions = [{'version_id': uid(810), 'series_id': uid(811), 'parent_version_id': None,
            'data_id': self.owner, 'version_number': 1, 'title': 'Original', 'message': '',
            'created_at': '2026-09-14T00:00:00Z', 'series_name': 'Paper revisions', 'head_version_id': uid(810), 'is_head': True}]
        self.groundings, self.knowledge, self.k_groundings = [], [], []
        self.compilations = []

    def transaction(self):
        return nullcontext()

    def execute(self, query, params=()):
        sql = ' '.join(query.split())
        self.calls.append((sql, deepcopy(params)))
        if sql.startswith('SET TRANSACTION'):
            result = None
        elif sql == 'SHOW transaction_read_only':
            result = {'transaction_read_only': self.read_only}
        elif "current_setting('server_version_num')" in sql:
            result = {'version': 180006}
        elif 'FROM pg_extension' in sql:
            result = {'extversion': '0.8.6'}
        elif "to_regclass('compiler_runtime.schema_migrations')" in sql:
            result = {'name': 'compiler_runtime.schema_migrations'}
        elif 'FROM compiler_runtime.schema_migrations' in sql:
            result = self.installed
        elif 'FROM canonical_store.data_versions ' in sql:
            result = [row for row in self.versions if not params or row['data_id'] == params[0]]
        elif 'FROM canonical_store.data_acquisitions ' in sql:
            result = [row for row in self.acquisitions if not params or row['data_id'] == params[0]]
        elif 'FROM canonical_store.data ' in sql:
            result = [row for row in self.data if not params or row['data_id'] == params[0]]
        elif "WHERE e.operation='i2k'" in sql:
            result = self.compilations
        elif 'FROM compiler_runtime.operation_executions e' in sql:
            field = 'execution_id' if 'WHERE e.execution_id=%s' in sql else 'data_id'
            result = [row for row in self.executions if not params or row[field] == params[0]]
        elif 'FROM canonical_store.knowledge_node_revisions r' in sql:
            result = self.knowledge
        elif 'FROM canonical_store.knowledge_node_groundings g' in sql:
            result = [row for row in self.k_groundings if row['data_id'] == params[0]]
        elif 'FROM canonical_store.knowledge_data_groundings' in sql:
            result = []
        elif 'FROM canonical_store.information_groundings' in sql:
            field = 'data_id' if 'g.data_id=%s' in sql else 'information_id'
            result = [row for row in self.groundings if row[field] == params[0]]
        elif 'FROM canonical_store.information i' in sql:
            if sql.startswith('SELECT i.*'):
                result = [row for row in self.units if row['information_id'] == params[0]]
            else:
                result = [{key: row.get(key) for key in ('information_id', 'data_id', 'origin_record_id', 'kind',
                    'unit_type', 'semantic_type', 'title', 'source_execution_id', 'ordinal')} | {
                        'character_count': len(row['content']), 'representation_schema': row['payload']['schema_version']}
                    for row in self.units if row['data_id'] == params[0]]
        else:
            raise AssertionError('Unexpected SQL: ' + sql)
        return SimpleNamespace(fetchone=lambda: deepcopy(result[0] if isinstance(result, list) and result else None if isinstance(result, list) else result),
                               fetchall=lambda: deepcopy(result))


class UnifiedSourceReadTests(unittest.TestCase):
    def test_source_only_knowledge_scope_uses_registered_data_without_a_wiki(self):
        service = desktop_read.DesktopReadService.__new__(desktop_read.DesktopReadService)
        service.dsn, service.wiki_id, service.include_data_ids = 'postgresql://unused', None, []
        with patch.object(desktop_read, 'connection', side_effect=lambda dsn: nullcontext(self.conn)):
            packets, owners = service._knowledge_scope()
        self.assertEqual(packets, [])
        self.assertEqual(owners, sorted(row['data_id'] for row in self.conn.data))

    def test_old_source_schema_has_no_canonical_parchments_and_is_not_migrated(self):
        result = self.service.dispatch({'operation': 'parchment_catalog'})
        self.assertEqual(result['parchments'], [])
        self.assertFalse(result['supported'])
        with self.assertRaises(PalimpsestError) as caught:
            self.service.dispatch({'operation': 'parchment_get', 'parchment_id': uid(920)})
        self.assertEqual(caught.exception.code, 'parchment_schema_not_installed')
        self.assertFalse(any('canonical_store.parchments' in sql for sql, _ in self.conn.calls))

    def test_prepared_i2k_is_not_reported_as_a_successful_model_run(self):
        self.conn.compilations = [{'execution_id': uid(915), 'state': 'prepared', 'successful_model_calls': 0,
            'other_model_calls': 0, 'created_or_revised_nodes': 0, 'reused_records': 0}]
        result = self.service.source_detail(self.conn.owner)
        self.assertEqual(result['i2k_executions'], self.conn.compilations)
        self.runtime.prepare_input.assert_not_called()
        sql = next(sql for sql, _ in self.conn.calls if "WHERE e.operation='i2k'" in sql)
        self.assertIn('compiler_runtime.k_input_information', sql)
        self.assertIn('i.data_id=%s', sql)

    def setUp(self):
        self.conn = FakeConnection()
        with patch.object(source_read, 'CompilerRuntime') as runtime:
            self.service = source_read.SourceReadService('postgresql://unused', '/unwritten/artifacts')
            self.runtime = runtime.return_value
        self.runtime.prepare_input.return_value = deepcopy(self.conn.packet)
        self.patch = patch.object(source_read, 'connection', side_effect=lambda dsn: nullcontext(self.conn))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_known_exact_old_schema_prefixes_are_read_only_without_wiki(self):
        for version in (6, 10, 13, 20):
            with self.subTest(version=version):
                conn = FakeConnection(version)
                result = source_read.SourceReadService._ready(conn)
                self.assertEqual(result['schema_version'], MIGRATIONS[version - 1])
                self.assertEqual(result['data_versions'], version >= 13)
                self.assertEqual(result['wiki_projection'], version >= 8)
                self.assertTrue(result['read_only'])
                self.assertFalse(any('wiki_projection.' in sql for sql, _ in conn.calls))
        self.assertIn('default_transaction_read_only=on', self.service.dsn)

    def test_changed_or_unknown_migration_and_writable_transactions_are_refused(self):
        for mutation in ('checksum', 'omitted', 'unknown', 'writable'):
            conn = FakeConnection(6)
            if mutation == 'checksum':
                conn.installed[0]['checksum'] = 'a' * 64
            elif mutation == 'omitted':
                conn.installed.pop(2)
            elif mutation == 'unknown':
                conn.installed.append({'version': 'unknown_schema', 'checksum': 'b' * 64})
            else:
                conn.read_only = 'off'
            with self.subTest(mutation=mutation), self.assertRaises(PalimpsestError):
                source_read.SourceReadService._ready(conn)

    def test_all_registered_data_including_no_i_or_wiki_survive_catalog(self):
        before = deepcopy((self.conn.data, self.conn.units, self.conn.executions))
        result = self.service.source_catalog()
        self.assertEqual(result['schema_version'], 'source-catalog-v1')
        self.assertEqual(len(result['data']), 2)
        web = result['data'][1]
        self.assertEqual(web['source_kind'], 'web')
        self.assertEqual(web['information_count'], 0)
        self.assertEqual(web['source_execution_count'], 0)
        self.assertEqual(web['acquisitions'][0]['origin_uri'], 'https://example.invalid/saved')
        self.assertEqual(result['data'][0]['information_count'], 1)
        self.assertFalse(result['capabilities']['wiki_projection'])
        self.assertEqual(before, (self.conn.data, self.conn.units, self.conn.executions))
        self.runtime.prepare_input.assert_not_called()
        self.assertTrue(all(sql.startswith(('SELECT ', 'SHOW ', 'SET TRANSACTION ')) for sql, _ in self.conn.calls))

    def test_detail_preserves_every_execution_version_and_information_identity(self):
        self.conn.installed = FakeConnection(13).installed
        self.conn.executions.append({**deepcopy(self.conn.executions[0]), 'execution_id': uid(901),
            'state': 'failed', 'error_code': 'retained_failure', 'information_count': 0})
        result = self.service.source_detail(self.conn.owner)
        self.assertEqual(len(result['executions']), 2)
        self.assertEqual(result['executions'][1]['error_code'], 'retained_failure')
        self.assertEqual(result['information'][0]['information_id'], self.conn.units[0]['information_id'])
        self.assertEqual(result['information'][0]['source_execution_id'], self.conn.packet['source_execution_id'])
        self.assertEqual(result['versions'], self.conn.versions)
        self.assertNotIn('content', result['information'][0])
        self.runtime.prepare_input.assert_not_called()

    def test_format_comes_from_mime_or_exact_code_provenance_not_a_filename_guess(self):
        data = {'data_id': 'a' * 64, 'filename': 'looks_like_code.py', 'media_type': 'text/plain'}
        self.assertEqual(source_read.source_kind(data), 'text')
        self.assertEqual(source_read.source_kind({**data, 'media_type': 'text/markdown'}), 'markdown')
        uri = 'palimpsest:codebase-snapshot:sha256:' + data['data_id']
        self.assertEqual(source_read.source_kind(data, acquisitions=[{'origin_uri': uri}]), 'code')
        self.assertEqual(source_read.source_kind(data, acquisitions=[{'origin_uri': uri + '0'}]), 'text')
        self.assertEqual(source_read.source_kind(data, [{'profile': {'transformation': {'algorithm': source_read.CODE_ALGORITHM}}}]), 'code')

    def test_owned_information_uses_full_verified_packet_and_keeps_exact_content_and_location(self):
        unit = self.conn.units[0]
        result = self.service.source_information(self.conn.owner, self.conn.packet['source_execution_id'], unit['information_id'])
        self.runtime.prepare_input.assert_called_once_with(self.conn.packet['source_execution_id'])
        self.assertEqual(result['content'], unit['content'])
        self.assertEqual(result['source_refs'], self.conn.packet['model_input']['information'][0]['source_refs'])
        self.assertEqual(result['verification']['method'], 'verified_complete_source_packet')
        self.assertEqual(result['original']['sha256'], self.conn.owner)
        self.assertTrue(result['read_only'])

    def test_information_cannot_switch_data_execution_record_or_packet_snapshot(self):
        for mutation in ('wrong_data', 'wrong_execution', 'wrong_record', 'changed_packet', 'changed_content'):
            conn = FakeConnection()
            self.conn = conn
            value = deepcopy(conn.packet)
            self.runtime.prepare_input.return_value = value
            owner, execution, information = conn.owner, conn.packet['source_execution_id'], conn.units[0]['information_id']
            if mutation == 'wrong_data':
                owner = '2' * 64
            elif mutation == 'wrong_execution':
                execution = uid(999)
            elif mutation == 'wrong_record':
                conn.units[0]['result_information_id'] = uid(999)
            elif mutation == 'changed_packet':
                value['data_id'] = '2' * 64
            else:
                value['model_input']['information'][0]['content'] = 'Rewritten source'
                value['input_sha256'] = digest({key: item for key, item in value.items() if key != 'input_sha256'})
            with self.subTest(mutation=mutation), self.assertRaises(PalimpsestError):
                self.service.source_information(owner, execution, information)

    def test_legacy_information_is_labeled_history_and_never_reparsed_or_mislabeled_complete(self):
        self.conn.executions[0]['profile'] = {'schema_version': 'd2i-v1'}
        self.conn.units[0]['payload'] = {'schema_version': 'information-v1', 'retained': 'old payload'}
        result = self.service.source_information(self.conn.owner, self.conn.packet['source_execution_id'], self.conn.units[0]['information_id'])
        self.assertEqual(result['payload'], self.conn.units[0]['payload'])
        self.assertEqual(result['verification']['method'], 'stored_legacy_information')
        self.assertFalse(result['verification']['source_packet_verified'])
        self.runtime.prepare_input.assert_not_called()

    def test_unknown_information_profile_never_becomes_a_silent_legacy_fallback(self):
        self.conn.executions[0]['profile'] = {'schema_version': 'future-source-profile'}
        with self.assertRaises(PalimpsestError) as caught:
            self.service.source_information(self.conn.owner, self.conn.packet['source_execution_id'], self.conn.units[0]['information_id'])
        self.assertEqual(caught.exception.code, 'source_information_profile_unavailable')
        self.runtime.prepare_input.assert_not_called()

    def test_knowledge_summaries_keep_historical_and_current_refs_with_only_selected_data_quotes(self):
        for ref in (uid(70), uid(71)):
            self.conn.knowledge.append({'knode_revision_id': ref, 'knode_id': uid(72), 'semantic_payload': {},
                'statement': 'Retained source claim', 'origin_record_id': uid(73), 'supersedes_revision_id': None,
                'created_at': '2026-09-14', 'kind': 'proposition', 'current_revision_id': uid(71),
                'origin_operation': 'i2k', 'record_disposition': 'accepted_new', 'identity_scope': 'general', 'source_data_id': None})
        self.conn.k_groundings = [{'data_id': self.conn.owner, 'node_revision_id': uid(70), 'quote': 'Selected source quote'},
                                 {'data_id': '2' * 64, 'node_revision_id': uid(70), 'quote': 'OUTSIDE_QUOTE_SENTINEL'}]
        result = self.service.source_detail(self.conn.owner)
        self.assertEqual([row['is_current_revision'] for row in result['knowledge']], [False, True])
        self.assertEqual(result['knowledge'][0]['generation_origin']['origin_record_id'], uid(73))
        self.assertNotIn('OUTSIDE_QUOTE_SENTINEL', json.dumps(result))

    def test_modern_detail_uses_transitive_data_membership_without_fabricating_direct_i(self):
        self.conn.installed = FakeConnection(13).installed
        self.conn.knowledge = [{'knode_revision_id': uid(70), 'knode_id': uid(72), 'semantic_payload': {},
            'statement': 'Accepted inferred claim', 'origin_record_id': uid(73), 'supersedes_revision_id': None,
            'created_at': '2026-09-14', 'kind': 'proposition', 'current_revision_id': uid(70),
            'origin_operation': 'k2k', 'record_disposition': 'accepted_new', 'identity_scope': 'general',
            'source_data_id': None, 'current_usable': False}]
        result = self.service.source_detail(self.conn.owner)
        self.assertTrue(result['knowledge'][0]['generation_origin']['is_inferred'])
        self.assertEqual(result['knowledge'][0]['groundings'], [])
        self.assertEqual(result['knowledge'][0]['current_applicability'], 'needs_revalidation')
        sql = next(sql for sql, _ in self.conn.calls if 'FROM canonical_store.knowledge_node_revisions' in sql)
        self.assertIn('canonical_store.derivation_source_data', sql)

    def test_unknown_write_fields_and_arbitrary_db_paths_are_rejected(self):
        for request in ({'operation': 'source_compile'}, {'operation': 'source_catalog', 'database': 'other'},
                {'operation': 'source_artifact', 'data_id': '../outside'}, {'operation': 'source_detail'},
                {'operation': 'source_information', 'data_id': self.conn.owner, 'source_execution_id': uid(1)},
                {'operation': 'source_artifact', 'data_id': self.conn.owner, 'source_execution_id': uid(1)},
                {'operation': 'source_artifact', 'data_id': self.conn.owner, 'sha256': None}):
            with self.subTest(request=request), self.assertRaises(PalimpsestError):
                self.service.dispatch(request)
        self.assertEqual(self.conn.calls, [])


class UnifiedSourceArtifactTests(unittest.TestCase):
    """Mocked registration and artifact delivery, with exact byte checks."""
    setUp = UnifiedSourceReadTests.setUp
    def register_bytes(self, raw, media_type):
        owner = sha256(raw).hexdigest()
        self.conn.data.append({'data_id': owner, 'media_type': media_type, 'byte_size': len(raw),
            'filename': 'retained', 'created_at': '2026-09-14'})
        self.runtime.store.read.return_value = raw
        return owner

    def test_original_text_html_unicode_and_line_endings_are_exact_and_never_rendered(self):
        raw = b'\xef\xbb\xbf<script>do_not_execute()</script>\r\n' + 'Cafe\u0301 μ'.encode()
        owner = self.register_bytes(raw, 'text/html; charset=UTF-8')
        result = self.service.source_artifact(owner)
        self.assertEqual(result['text'].encode('utf-8'), raw)
        self.assertEqual(result['sha256'], owner)
        self.assertNotIn('base64', result)
        self.assertTrue(result['verified'])
        self.runtime.prepare_input.assert_not_called()

    def test_pdf_and_non_utf8_keep_original_bytes_and_hashes(self):
        for raw, mime in ((b'%PDF-1.7\nretained fixture', 'application/pdf'), (b'\xff\xfe\x00a', 'text/plain')):
            with self.subTest(mime=mime):
                owner = self.register_bytes(raw, mime)
                result = self.service.source_artifact(owner)
                self.assertEqual(b64decode(result['base64']), raw)
                self.assertNotIn('text', result)

    def test_unowned_media_original_tampering_and_oversized_transport_fail_closed(self):
        owner = self.register_bytes(b'retained', 'text/plain')
        self.runtime.store.read.return_value = b'rewritten'
        with self.assertRaises(PalimpsestError) as caught:
            self.service.source_artifact(owner)
        self.assertEqual(caught.exception.code, 'source_artifact_changed')
        self.conn.data[-1]['byte_size'] = source_read.MAX_ARTIFACT_BYTES + 1
        with self.assertRaises(PalimpsestError) as caught:
            self.service.source_artifact(owner)
        self.assertEqual(caught.exception.code, 'source_artifact_too_large')
        with self.assertRaises(PalimpsestError):
            self.service.source_artifact(self.conn.owner, sha256='3' * 64)
        with self.assertRaises(PalimpsestError):
            self.service.source_artifact(self.conn.owner, source_execution_id=self.conn.packet['source_execution_id'])
        with self.assertRaises(PalimpsestError) as caught:
            self.service.source_artifact(self.conn.owner, self.conn.packet['source_execution_id'], '3' * 64)
        self.assertEqual(caught.exception.code, 'source_media_owner_mismatch')

    def test_owned_media_without_a_wiki_uses_the_exact_completed_source_packet(self):
        raw = b'\x89PNG\r\n\x1a\nretained synthetic asset'
        checksum = sha256(raw).hexdigest()
        value = deepcopy(self.conn.packet)
        value['model_input']['information'][0]['media'] = [{'sha256': checksum, 'byte_size': len(raw)}]
        value['input_sha256'] = digest({key: item for key, item in value.items() if key != 'input_sha256'})
        self.runtime.prepare_input.return_value = value
        self.runtime.derived.read.return_value = raw
        result = self.service.source_artifact(self.conn.owner, value['source_execution_id'], checksum)
        self.assertEqual(result['media_type'], 'image/png')
        self.assertEqual(b64decode(result['base64']), raw)
        self.assertEqual(result['data_id'], self.conn.owner)
        self.runtime.store.read.assert_not_called()

    @unittest.skipUnless(sys.platform == 'linux', 'Requires no-follow Linux Artifact Store reads')
    def test_real_artifact_read_creates_no_files_and_rejects_symlink_escape(self):
        with TemporaryDirectory(prefix='source-read-artifact-') as temporary:
            root = Path(temporary)
            raw = b'# Retained source\r\nExact source bytes.\r\n'
            owner = self.register_bytes(raw, 'text/markdown')
            stored = root / 'artifacts' / 'objects' / 'sha256' / owner[:2] / owner
            stored.parent.mkdir(parents=True)
            stored.write_bytes(raw)
            self.runtime.store = ArtifactStore(root / 'artifacts')
            before = {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}
            result = self.service.source_artifact(owner)
            self.assertEqual(result['text'].encode(), raw)
            self.assertEqual(before, {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()})
            outside = root / 'outside.md'
            outside.write_bytes(raw)
            stored.unlink()
            stored.symlink_to(outside)
            with self.assertRaises(PalimpsestError) as caught:
                self.service.source_artifact(owner)
            self.assertEqual(caught.exception.code, 'unsafe_path')


class UnifiedSourceBridgeTests(unittest.TestCase):
    def test_source_only_bridge_routes_source_and_knowledge_but_rejects_wiki_calls(self):
        path = Path(__file__).resolve().parents[2] / 'tools/desktop_bridge.py'
        spec = importlib.util.spec_from_file_location('unified_source_bridge_test', path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        source = MagicMock()
        source.dispatch.return_value = {'schema_version': 'source-catalog-v1', 'data': [], 'read_only': True}
        knowledge = MagicMock()
        knowledge.dispatch.return_value = {'nodes': [], 'sources': [], 'data_versions': [], 'read_only': True}
        routed = bridge.DesktopServices(source, knowledge=knowledge)
        output = io.StringIO()
        bridge.serve(routed, io.StringIO('{"request_id":"source","operation":"source_catalog"}\n'
            '{"request_id":"knowledge","operation":"knowledge_catalog"}\n'
            '{"request_id":"wiki","operation":"catalog"}\n'), output)
        values = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(values[0]['result']['schema_version'], 'source-catalog-v1')
        self.assertEqual(values[1]['result']['nodes'], [])
        self.assertEqual(values[2]['error']['code'], 'desktop_wiki_not_configured')
        wiki = MagicMock()
        bridge.DesktopServices(source, wiki).dispatch({'operation': 'catalog'})
        wiki.dispatch.assert_called_once_with({'operation': 'catalog'})

    def test_bridge_main_initializes_store_knowledge_without_requiring_a_wiki(self):
        path = Path(__file__).resolve().parents[2] / 'tools/desktop_bridge.py'
        spec = importlib.util.spec_from_file_location('unified_source_bridge_main_test', path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        with patch.object(bridge, 'load_config', return_value=SimpleNamespace(database_dsn='postgresql://unused', artifact_root='/artifacts')), \
                patch.object(bridge, 'SourceReadService') as sources, patch.object(bridge, 'DesktopReadService') as wiki, \
                patch.object(bridge, 'serve') as serve, patch.object(sys, 'argv', ['desktop_bridge.py', '--database-name', 'registered_sources']):
            self.assertEqual(bridge.main(), 0)
            wiki.assert_called_once_with('host=unused dbname=registered_sources', '/artifacts', None, '/query', include_data_ids=None)
            self.assertIsNone(serve.call_args.args[0].wiki)
            self.assertIs(serve.call_args.args[0].knowledge, wiki.return_value)
            self.assertIs(serve.call_args.args[0].sources, sources.return_value)


if __name__ == '__main__':
    unittest.main()
