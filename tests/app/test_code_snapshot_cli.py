"""The source snapshot utility runs headlessly without a database or a model."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.cli import main


class CodeSnapshotCliTests(unittest.TestCase):
    def test_snapshot_locate_verify_restore_without_loading_database_config(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            raw = b'def example():\r\n    return 3'
            (root / 'src/example.py').write_bytes(raw)
            destination = root / 'snapshot'
            def call(*args):
                output = StringIO()
                with patch('palimpsest.cli.load_config', side_effect=AssertionError('No database required')), redirect_stdout(output):
                    status = main(['code', *map(str, args), '--json', '--non-interactive'])
                self.assertEqual(status, 0, output.getvalue())
                return json.loads(output.getvalue())['result']
            manifest = call('snapshot', root, destination)
            self.assertEqual(call('verify', destination, '--data-id', manifest['dossier_sha256']), manifest)
            entry = manifest['files'][0]
            located = call('locate', destination, '--byte-range', entry['body_byte_start'], entry['body_byte_end'])
            self.assertEqual(located['matches'][0]['path'], 'src/example.py')
            restored = root / 'restored'
            call('restore', destination, restored)
            self.assertEqual((restored / 'src/example.py').read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
