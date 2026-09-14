"""Exact generated dossier round trips and source boundaries; no application DB."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest import code_snapshot as snapshot


class CodeSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix='code-snapshot-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'src').mkdir()
        self.raw = b'\xef\xbb\xbf# comment\r\nvalue = "````"\r\n# \xf0\x9f\x98\x80 Cafe\xcc\x81\r\nlast = 1'
        (self.root / 'src/example.py').write_bytes(self.raw)
        (self.root / 'README.md').write_bytes(b'# Title\n\nExact documentation.\n')

    def test_deterministic_snapshot_embedded_manifest_and_exact_restoration(self):
        first = snapshot.snapshot(self.root, self.root / 'first')
        second = snapshot.snapshot(self.root, self.root / 'second')
        self.assertEqual(first, second)
        dossier = (self.root / 'first/dossier.md').read_bytes()
        self.assertEqual(dossier, (self.root / 'second/dossier.md').read_bytes())
        self.assertIn(b'`````\n' + self.raw + b'\n`````', dossier)
        self.assertEqual(snapshot.verify(self.root / 'first', first['dossier_sha256']), first)
        restored = snapshot.restore(self.root / 'first', self.root / 'restored')
        self.assertEqual(restored['count'], 2)
        self.assertEqual((self.root / 'restored/src/example.py').read_bytes(), self.raw)
        self.assertEqual((self.root / 'src/example.py').read_bytes(), self.raw)

    def test_exact_unicode_and_crlf_positions_map_back_to_source_lines(self):
        manifest = snapshot.snapshot(self.root, self.root / 'snapshot')
        entry = next(e for e in manifest['files'] if e['path'] == 'src/example.py')
        source = self.raw.decode('utf-8')
        start, end = source.index('😀'), source.index('😀') + len('😀 Cafe\u0301')
        match = snapshot.locate(self.root / 'snapshot', char_range=[entry['body_char_start'] + start, entry['body_char_start'] + end])
        self.assertEqual(match['unmapped_ranges'], [])
        self.assertEqual(match['matches'][0]['source_char_range'], [start, end])
        self.assertEqual(match['matches'][0]['line_range'], [3, 3])
        a, b = match['matches'][0]['source_byte_range']
        self.assertEqual(self.raw[a:b].decode(), '😀 Cafe\u0301')
        byte_match = snapshot.locate(self.root / 'snapshot', byte_range=[entry['body_byte_start'] + a, entry['body_byte_start'] + b])
        self.assertEqual(byte_match['matches'][0]['source_char_range'], [start, end])
        first_line_end = source.index('\n') + 1
        line = snapshot.locate(self.root / 'snapshot', char_range=[entry['body_char_start'], entry['body_char_start'] + first_line_end])
        self.assertEqual(line['matches'][0]['line_range'], [1, 1])
        wrapper = snapshot.locate(self.root / 'snapshot', byte_range=[0, 20])
        self.assertEqual(wrapper['matches'], [])
        self.assertEqual(wrapper['unmapped_ranges'], [[0, 20]])

    def test_a_new_source_file_during_capture_cannot_be_silently_omitted(self):
        read = snapshot._read_stable
        def add_source(path):
            raw = read(path)
            (self.root / 'src/added.py').write_bytes(b'new = 1\n')
            return raw
        output = self.root / 'snapshot'
        with patch.object(snapshot, '_read_stable', side_effect=add_source):
            with self.assertRaisesRegex(ValueError, 'snapshot_source_changed'):
                snapshot.snapshot(self.root, output)
        self.assertFalse(output.exists())

    def test_default_excludes_generated_sensitive_and_binary_without_copying(self):
        (self.root / 'src/.env').write_text('must not appear')
        (self.root / 'src/credentials.json').write_text('must not appear')
        (self.root / 'src/binary.dat').write_bytes(b'\xff\x00')
        (self.root / 'src/__pycache__').mkdir()
        (self.root / 'src/__pycache__/generated.pyc').write_bytes(b'generated')
        manifest = snapshot.snapshot(self.root, self.root / 'snapshot')
        self.assertEqual(len(manifest['files']), 2)
        self.assertEqual(len(manifest['excluded']), 4)
        self.assertNotIn(b'must not appear', (self.root / 'snapshot/dossier.md').read_bytes())
        with self.assertRaises(ValueError):
            snapshot.snapshot(self.root, self.root / 'explicit', ['src/binary.dat'])

    def test_no_overwrite_path_escape_and_case_collisions(self):
        snapshot.snapshot(self.root, self.root / 'snapshot')
        with self.assertRaises(ValueError):
            snapshot.snapshot(self.root, self.root / 'snapshot')
        for paths in (['../outside.py'], ['/absolute.py'], ['src/example.py', 'src/example.py']):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                snapshot.snapshot(self.root, self.root / 'bad', paths)
        with self.assertRaises(ValueError):
            snapshot.snapshot(self.root, self.root.parent / 'escape-output')
        with self.assertRaises(ValueError):
            snapshot.restore(self.root / 'snapshot', self.root / 'src')

    def test_mutated_source_is_detected_before_output_publication(self):
        original_read = snapshot._read_stable
        changed = False
        def mutate(path):
            nonlocal changed
            raw = original_read(path)
            if Path(path).name == 'example.py' and not changed:
                changed = True
                Path(path).write_bytes(raw + b'\nchanged = True')
            return raw
        with patch.object(snapshot, '_read_stable', side_effect=mutate), self.assertRaisesRegex(ValueError, 'source_changed'):
            snapshot.snapshot(self.root, self.root / 'snapshot')
        self.assertFalse((self.root / 'snapshot').exists())

    def test_corrupt_dossier_sidecar_and_embedded_path_traversal_are_rejected(self):
        manifest = snapshot.snapshot(self.root, self.root / 'snapshot')
        directory = self.root / 'snapshot'
        raw = (directory / 'dossier.md').read_bytes()
        (directory / 'dossier.md').write_bytes(raw.replace(b'last = 1', b'last = 2'))
        with self.assertRaises(ValueError):
            snapshot.verify(directory)
        (directory / 'dossier.md').write_bytes(raw)
        changed = deepcopy(manifest); changed['files'][0]['path'] = '../escape'
        embedded = {k: v for k, v in changed.items() if k not in ('dossier_sha256', 'dossier_byte_size')}
        tampered = raw[:raw.rfind(snapshot.FOOTER)] + snapshot.FOOTER + snapshot._json(embedded) + snapshot.ENDING
        changed.update(dossier_sha256=sha256(tampered).hexdigest(), dossier_byte_size=len(tampered))
        (directory / 'dossier.md').write_bytes(tampered)
        (directory / 'manifest.json').write_text(json.dumps(changed), encoding='utf-8')
        with self.assertRaises(ValueError):
            snapshot.restore(directory, self.root / 'restored')
        self.assertFalse((self.root / 'restored').exists())

    def test_symlink_inputs_are_rejected_when_platform_allows_creation(self):
        link = self.root / 'src/link.py'
        try:
            link.symlink_to(self.root / 'src/example.py')
        except OSError:
            self.skipTest('Creating symlinks requires OS permission; guards also inspect Windows reparse flags.')
        with self.assertRaises(ValueError):
            snapshot.snapshot(self.root, self.root / 'snapshot')

    def test_retained_bytes_compare_and_restore_without_sidecars_or_live_sources(self):
        (self.root / 'src/remove.py').write_bytes(b'exact removed bytes\n')
        snapshot.snapshot(self.root, self.root / 'first')
        before = (self.root / 'first/dossier.md').read_bytes()
        (self.root / 'README.md').write_bytes(b'# Title\nChanged documentation.\n')
        (self.root / 'src/remove.py').rename(self.root / 'src/add.py')
        snapshot.snapshot(self.root, self.root / 'second')
        after = (self.root / 'second/dossier.md').read_bytes()
        (self.root / 'first/manifest.json').unlink()
        (self.root / 'second/manifest.json').unlink()
        (self.root / 'src/example.py').write_bytes(b'live checkout is now unrelated')
        result = snapshot.compare(before, after)
        self.assertEqual(result['added'], ['src/add.py'])
        self.assertEqual(result['removed'], ['src/remove.py'])
        self.assertEqual(result['changed'], ['README.md'])
        self.assertEqual(result['unchanged'], ['src/example.py'])
        self.assertNotIn('renamed', result)
        self.assertEqual(result['before_data_id'], sha256(before).hexdigest())
        self.assertEqual(result['after_data_id'], sha256(after).hexdigest())
        restored = snapshot.restore_bytes(before, self.root / 'restored', result['before_data_id'])
        self.assertEqual(restored['count'], 3)
        self.assertEqual((self.root / 'restored/src/example.py').read_bytes(), self.raw)
        self.assertTrue((self.root / 'restored/src/remove.py').exists())
        self.assertFalse((self.root / 'restored/src/add.py').exists())

    def test_byte_manifest_checks_member_headers_body_hashes_and_expected_Data_hash(self):
        original = snapshot.snapshot(self.root, self.root / 'snapshot')
        raw = (self.root / 'snapshot/dossier.md').read_bytes()
        self.assertEqual(snapshot.manifest_from_bytes(raw, original['dossier_sha256']), original)
        with self.assertRaisesRegex(ValueError, 'snapshot_manifest_mismatch'):
            snapshot.manifest_from_bytes(raw, '0' * 64)
        with self.assertRaisesRegex(ValueError, 'snapshot_member_header_mismatch'):
            snapshot.manifest_from_bytes(raw.replace(b'## File: "README.md"', b'## File: "ELSEXX.md"'))
        with self.assertRaisesRegex(ValueError, 'snapshot_member_content_mismatch'):
            snapshot.compare(raw, raw.replace(b'last = 1', b'last = 2'))
        embedded = {key: value for key, value in original.items()
                    if key not in ('dossier_sha256', 'dossier_byte_size')}
        embedded['files'][0]['path'] = 'forged/README.md'
        renamed = raw[:raw.rfind(snapshot.FOOTER)] + snapshot.FOOTER + snapshot._json(embedded) + snapshot.ENDING
        with self.assertRaisesRegex(ValueError, 'snapshot_member_header_mismatch'):
            snapshot.restore_bytes(renamed, self.root / 'invalid-restoration')
        self.assertFalse((self.root / 'invalid-restoration').exists())


if __name__ == '__main__':
    unittest.main()
