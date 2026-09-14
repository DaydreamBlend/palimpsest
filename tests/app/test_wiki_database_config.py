"""Database-name selection and thin Wiki CLI routing; no network or storage."""

from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from psycopg.conninfo import conninfo_to_dict

from palimpsest import cli
from palimpsest.config import Config, select_database
from palimpsest.errors import PalimpsestError
from test_multi_source_i2k import uid


class WikiDatabaseConfigTests(unittest.TestCase):
    def test_database_name_changes_only_database_and_handles_literal_punctuation(self):
        dsn = "postgresql://fixture:synthetic%20password@localhost:5433/old?sslmode=disable"
        before = conninfo_to_dict(dsn)
        self.assertEqual(select_database(dsn), dsn)
        selected = conninfo_to_dict(select_database(dsn, "new ' database ; dbname=other"))
        self.assertEqual(selected.pop('dbname'), "new ' database ; dbname=other")
        before.pop('dbname')
        self.assertEqual(selected, before)

    def test_invalid_names_and_dsn_do_not_expose_secret_in_errors_or_config_repr(self):
        secret = 'synthetic-secret-do-not-print'
        dsn = f'host=localhost user=test password={secret} dbname=palimpsest'
        for name in ('', '   ', 'bad\nname', 'bad\x00name', 'a' * 64, '한' * 22, 42):
            with self.subTest(name_type=type(name).__name__), self.assertRaises(PalimpsestError) as caught:
                select_database(dsn, name)
            self.assertNotIn(secret, str(caught.exception))
            self.assertEqual(caught.exception.code, 'invalid_database_name')
        with self.assertRaises(PalimpsestError) as caught:
            select_database(f'unknown_option={secret}', 'palimpsest')
        self.assertEqual(caught.exception.code, 'invalid_configuration')
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(secret, repr(Config(dsn, Path('/synthetic'), 'local')))

    def test_public_database_sync_options_forward_exact_request_and_head(self):
        args = cli._parser().parse_args(['wiki', 'database-sync', '--wiki-id', uid(1),
            '--request-id', uid(2), '--expected-head', uid(3), '--directory', '/synthetic/wiki',
            '--database-name', 'fixture_wiki', '--json'])
        config = Config('host=localhost user=fixture password=synthetic dbname=palimpsest', Path('/artifacts'), 'fixture')
        runtime = Mock()
        with patch('palimpsest.wiki_database.WikiDatabase', return_value=runtime) as constructor:
            cli._wiki(args, config)
        selected, artifact_root = constructor.call_args.args
        self.assertEqual(conninfo_to_dict(selected)['dbname'], 'fixture_wiki')
        self.assertEqual(artifact_root, config.artifact_root)
        runtime.sync.assert_called_once_with(uid(1), uid(2), Path('/synthetic/wiki'),
                                             expected_head=uid(3), review_annotations=None)

    def test_related_cli_forwards_historical_checkpoint_and_review_visibility(self):
        args = cli._parser().parse_args(['wiki', 'database-related', '--wiki-id', uid(1),
            '--page-id', uid(4), '--import-id', uid(2), '--include-review-required'])
        config = Config('host=localhost dbname=palimpsest', Path('/artifacts'), 'fixture')
        runtime = Mock()
        with patch('palimpsest.wiki_database.WikiDatabase', return_value=runtime):
            cli._wiki(args, config)
        runtime.related.assert_called_once_with(uid(1), uid(4), include_review_required=True, import_id=uid(2))
        args = cli._parser().parse_args(['db', 'migrate', '--database-name', 'palimpsest', '--json'])
        self.assertEqual(args.database_name, 'palimpsest')


if __name__ == '__main__':
    unittest.main()
