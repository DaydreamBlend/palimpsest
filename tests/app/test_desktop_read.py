"""Desktop read contracts: real Linux files and isolated PostgreSQL fixtures."""

from base64 import b64decode
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.canonical_store import connection
from palimpsest.desktop_read import DesktopReadService
from palimpsest.errors import PalimpsestError
from palimpsest.wiki_projection_store import ProjectionStore
from palimpsest.wiki_query import normalize_answer, validate_answer
import test_wiki_database as database_fixtures
import test_paper_wiki_runtime as paper_fixtures
import test_wiki_query as query_fixtures
from test_multi_source_i2k import uid


class BridgeTests(unittest.TestCase):
    def test_json_line_transport_survives_bad_request_without_exposing_exception(self):
        path = Path(__file__).resolve().parents[2] / 'tools/desktop_bridge.py'
        spec = importlib.util.spec_from_file_location('desktop_bridge_test', path)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        class Service:
            def dispatch(self, request):
                if request['operation'] == 'bad':
                    raise RuntimeError('secret=must-not-appear')
                return {'read_only': True}
        output = io.StringIO()
        bridge.serve(Service(), io.StringIO('\n'.join((
            '{"request_id":"bad","operation":"bad"}',
            'malformed', '{"request_id":"good","operation":"catalog"}'))), output)
        values = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(values[-1]['result'], {'read_only': True})
        self.assertEqual(values[-1]['request_id'], 'good')
        self.assertEqual(values[0]['error']['code'], 'desktop_read_failed')
        self.assertNotIn('secret', output.getvalue())


@unittest.skipUnless(sys.platform == 'linux', 'Requires Linux no-follow filesystem primitives')
class DesktopQueryReadTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='desktop-query-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = ProjectionStore(self.root / 'query')
        self.context = query_fixtures.context()
        self.service = DesktopReadService('postgresql://unused', self.root / 'artifacts',
                                          self.context['wiki_id'], self.store.root)
        self.answer = normalize_answer(query_fixtures.proposal(), self.context)
        self.validation = validate_answer(query_fixtures.decision(self.answer), self.answer)
        self.job = {**{key: self.context[key] for key in
                      ('query_id', 'wiki_id', 'import_id', 'index_id', 'question', 'round', 'layer')},
                    'state': 'answered'}
        self.relative = f"queries/{self.job['query_id']}/rounds/0"
        self.store.write_json(self.relative + '/proposal.json', self.answer)
        self.store.write_json(self.relative + '/validation.json', self.validation)

    def read(self):
        with patch.object(self.service, '_job', return_value=deepcopy(self.job)):
            return self.service.query(self.job['query_id'])

    def test_accepted_held_and_attention_do_not_fall_back_to_prior_answer(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = self.read()
        self.assertTrue(result['accepted'])
        self.assertIn('처치 A에서 3 μm', result['answer'])
        for state in ('needs_attention', 'needs_review', 'invalid_response'):
            self.job.update(state=state, prior_answer_path='outside/secret')
            result = self.read()
            self.assertFalse(result['accepted'])
            self.assertIsNone(result['answer'])
            self.assertEqual(result['rounds'][0]['proposal'], self.answer)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                 for p in self.root.rglob('*') if p.is_file()})

    def test_tampered_acceptance_and_symlink_read_are_rejected(self):
        changed = deepcopy(self.validation)
        changed['claims'][0]['supported'] = False
        self.store.replace_json(self.relative + '/validation.json', changed)
        with self.assertRaises(PalimpsestError):
            self.read()
        path = self.store.root / self.relative / 'validation.json'
        path.unlink()
        outside = self.root / 'outside.json'
        outside.write_text(json.dumps(self.validation))
        path.symlink_to(outside)
        with self.assertRaises(PalimpsestError) as caught:
            self.read()
        self.assertEqual(caught.exception.code, 'unsafe_path')

    def test_unknown_operation_fields_and_path_ids_never_dispatch(self):
        for request in ({'operation': 'sync'}, {'operation': 'catalog', 'directory': '/etc'},
                        {'operation': 'information', 'information_id': '../secret', 'source_execution_id': uid(1)},
                        {'operation': 'query', 'query_id': '../secret'}, {'operation': 'page'},
                        {'operation': 'artifact', 'kind': 'original', 'data_id': '/etc/passwd'}):
            with self.subTest(request=request), self.assertRaises(PalimpsestError):
                self.service.dispatch(request)


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('PALIMPSEST_TEST_DSN'),
                     'Requires explicitly selected fixture PostgreSQL database named palimpsest')
class DesktopReadPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_fixtures.WikiDatabaseTests.setUpClass.__func__(cls)

    compile = database_fixtures.WikiDatabaseTests.compile
    edit_paper = database_fixtures.WikiDatabaseTests.edit_paper

    def setUp(self):
        database_fixtures.WikiDatabaseTests.setUp(self)
        self.database.import_archive(self.wiki_id, self.import_id, self.archive)
        self.desktop = DesktopReadService(self.dsn, self.base / 'artifacts', self.wiki_id, self.base / 'query')

    def test_catalog_page_exact_i_original_and_database_reads_preserve_state(self):
        before = paper_fixtures.PaperWikiPostgresTests.canonical_state(self)
        catalog = self.desktop.dispatch({'operation': 'catalog'})
        self.assertEqual(len(catalog['pages']), 2)
        paper = next(page for page in catalog['pages'] if page['kind'] == 'paper')
        page = self.desktop.page(paper['page_id'])
        citation = page['page']['items'][0]['evidence'][0]
        unit = self.desktop.information(citation['information_id'], citation['source_execution_id'])
        self.assertEqual(unit['data_id'], self.owner)
        self.assertEqual(unit['content'][citation['char_start']:citation['char_end']], citation['quote'])
        original = self.desktop.artifact('original', self.owner)
        self.assertEqual(b64decode(original['base64']), (self.base / 'fixture.md').read_bytes())
        with self.assertRaises(PalimpsestError):
            self.desktop.information(citation['information_id'], self.repository.allocate_id())
        with self.assertRaises(PalimpsestError):
            self.desktop.artifact('original', 'a' * 64)
        with self.assertRaises(PalimpsestError):
            self.desktop.artifact('image', self.owner, sha256='b' * 64)
        with connection(self.desktop.dsn) as conn:
            self.assertEqual(conn.execute('SHOW default_transaction_read_only').fetchone()['default_transaction_read_only'], 'on')
        self.assertEqual(paper_fixtures.PaperWikiPostgresTests.canonical_state(self), before)
        self.assertFalse((self.base / 'query').exists())

    def test_history_uses_exact_import_and_topic_paper_snapshot(self):
        old_catalog = self.desktop.catalog()
        old_paper = next(p for p in old_catalog['pages'] if p['kind'] == 'paper')
        old_topic = next(p for p in old_catalog['pages'] if p['kind'] == 'topic')
        self.edit_paper()
        new_import = self.repository.allocate_id()
        self.database.import_archive(self.wiki_id, new_import, self.archive, expected_head=self.import_id)
        historical = self.desktop.page(old_paper['page_id'], old_paper['snapshot_id'])
        self.assertEqual(historical['import_id'], self.import_id)
        self.assertEqual(historical['related']['snapshot_id'], old_paper['snapshot_id'])
        self.assertEqual(len(historical['history']), 2)
        topic = self.desktop.page(old_topic['page_id'], old_topic['snapshot_id'])
        self.assertEqual(topic['topic_sources'][0]['snapshot_id'], old_paper['snapshot_id'])
        self.assertEqual(topic['import_id'], self.import_id)


if __name__ == '__main__':
    unittest.main()
