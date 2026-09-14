"""No-DB checks for exact historical Wiki schema reads without implicit migration."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from palimpsest.canonical_store import MIGRATIONS, migration_source
from palimpsest.errors import PalimpsestError
from palimpsest.wiki_database import WikiDatabase
from palimpsest import wiki_database


class WikiSchemaCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = [{'version': name, 'checksum': migration_source(name)[1]} for name in MIGRATIONS]

    def connection(self, installed, read_only='on'):
        conn = Mock()
        values = {
            "SELECT current_setting('server_version_num')::integer AS version": {'version': 180000},
            "SELECT extversion FROM pg_extension WHERE extname='vector'": {'extversion': '0.8.6'},
            "SELECT to_regclass('wiki_projection.imports') AS name": {'name': 'wiki_projection.imports'},
            'SELECT version,checksum FROM compiler_runtime.schema_migrations ORDER BY version': installed,
            'SHOW transaction_read_only': {'transaction_read_only': read_only},
        }
        def execute(statement):
            if statement not in values:
                raise AssertionError('Schema compatibility must perform only these reads: ' + str(statement))
            return Mock(fetchone=Mock(return_value=deepcopy(values[statement])),
                        fetchall=Mock(return_value=deepcopy(values[statement])))
        conn.execute.side_effect = execute
        return conn

    def assert_rejected(self, installed, read_only='on'):
        conn = self.connection(installed, read_only)
        with self.assertRaises(PalimpsestError) as raised:
            WikiDatabase._ready(conn)
        self.assertEqual(raised.exception.code, 'wiki_database_schema_mismatch')
        return conn

    def test_current_exact_schema_preserves_normal_read_write_access(self):
        for mode in ('on', 'off'):
            with self.subTest(read_only=mode):
                conn = self.connection(self.expected, mode)
                WikiDatabase._ready(conn)
                self.assertNotIn('SHOW transaction_read_only', [call.args[0] for call in conn.execute.call_args_list])

    def test_preserved_paper_wiki_0010_prefix_is_read_only_and_every_checksum_is_required(self):
        installed = deepcopy(self.expected[:10])
        self.assertEqual(installed[-1]['version'], '0010_wiki_retrieval')
        before = deepcopy(installed)
        conn = self.connection(installed, 'on')
        WikiDatabase._ready(conn)
        self.assertEqual(conn.execute.call_args_list[-1].args, ('SHOW transaction_read_only',))
        self.assertEqual(installed, before)
        for mode in ('off', '', True, 'on '):
            with self.subTest(read_only=mode):
                self.assert_rejected(installed, mode)
        for ordinal in range(len(installed)):
            with self.subTest(changed_migration=ordinal):
                changed = deepcopy(installed)
                changed[ordinal]['checksum'] = '0' * 64
                self.assert_rejected(changed)

    def test_only_exact_13_14_and_15_prefixes_allow_transaction_read_only_on(self):
        for count, version in ((13, '0013_data_versions'), (14, '0014_user_requested_d2k'),
                               (15, '0015_explicit_knowledge_revision')):
            with self.subTest(version=version):
                installed = self.expected[:count]
                self.assertEqual(installed[-1]['version'], version)
                conn = self.connection(installed)
                WikiDatabase._ready(conn)
                self.assertEqual(conn.execute.call_args_list[-1].args, ('SHOW transaction_read_only',))
                self.assertEqual(installed, self.expected[:count])

    def test_historical_prefixes_reject_write_transactions_or_unconfirmed_read_only_mode(self):
        for count in (13, 14, 15):
            for mode in ('off', '', True, 'on '):
                with self.subTest(prefix=count, read_only=mode):
                    self.assert_rejected(self.expected[:count], mode)

    def test_checksum_mismatch_anywhere_in_historical_or_current_schema_is_rejected(self):
        for count in (13, 14, 15, len(self.expected)):
            for ordinal in (0, count - 1):
                with self.subTest(prefix=count, ordinal=ordinal):
                    installed = deepcopy(self.expected[:count])
                    installed[ordinal]['checksum'] = '0' * 64
                    conn = self.assert_rejected(installed)
                    self.assertNotIn('SHOW transaction_read_only', [call.args[0] for call in conn.execute.call_args_list])

    def test_older_unknown_newer_missing_duplicate_and_out_of_order_schemas_are_rejected(self):
        unknown = deepcopy(self.expected[:13])
        unknown[-1]['version'] = '0013_unrecognized_schema'
        changed_order = deepcopy(self.expected[:14])
        changed_order[0], changed_order[1] = changed_order[1], changed_order[0]
        malformed = [[], self.expected[:12], unknown, changed_order,
            self.expected + [{'version': '9999_future_schema', 'checksum': 'a' * 64}],
            self.expected[:5] + self.expected[6:14], self.expected[:3] + self.expected[2:14]]
        for installed in malformed:
            with self.subTest(versions=[row['version'] for row in installed]):
                self.assert_rejected(installed)

    def test_exact_16_prefix_is_read_only_after_additive_17(self):
        historical = self.expected[:16]
        self.assertEqual(historical[-1]['version'], '0016_propagation_worker')
        future = [*historical, {'version': '0017_synthetic_registry', 'checksum': 'f' * 64}]
        checksums = {row['version']: row['checksum'] for row in future}
        with patch.object(wiki_database, 'MIGRATIONS', tuple(checksums)), \
                patch.object(wiki_database, 'migration_source', side_effect=lambda name: ('', checksums[name])):
            WikiDatabase._ready(self.connection(historical, 'on'))
            self.assert_rejected(historical, 'off')
            corrupted = deepcopy(historical)
            corrupted[-1]['checksum'] = '0' * 64
            self.assert_rejected(corrupted)

    def test_exact_17_prefix_is_read_only_after_additive_18(self):
        historical = self.expected[:17]
        self.assertEqual(historical[-1]['version'], '0017_n2e_relations')
        future = [*historical, {'version': '0018_synthetic_guards', 'checksum': 'f' * 64}]
        checksums = {row['version']: row['checksum'] for row in future}
        with patch.object(wiki_database, 'MIGRATIONS', tuple(checksums)), \
                patch.object(wiki_database, 'migration_source', side_effect=lambda name: ('', checksums[name])):
            WikiDatabase._ready(self.connection(historical, 'on'))
            self.assert_rejected(historical, 'off')
            corrupted = deepcopy(historical)
            corrupted[-1]['checksum'] = '0' * 64
            self.assert_rejected(corrupted)


    def test_exact_18_prefix_is_read_only_after_additive_19(self):
        historical = self.expected[:18]
        self.assertEqual(historical[-1]['version'], '0018_n2e_review_agreement')
        future = [*historical, {'version': '0019_synthetic_fence', 'checksum': 'f' * 64}]
        checksums = {row['version']: row['checksum'] for row in future}
        with patch.object(wiki_database, 'MIGRATIONS', tuple(checksums)), \
                patch.object(wiki_database, 'migration_source', side_effect=lambda name: ('', checksums[name])):
            WikiDatabase._ready(self.connection(historical, 'on'))
            self.assert_rejected(historical, 'off')


if __name__ == '__main__':
    unittest.main()
