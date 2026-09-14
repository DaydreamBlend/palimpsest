"""Native PDF view fidelity and host isolation; no DB, I, parser or model calls."""
from copy import deepcopy
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest import d2k_pdf, pdf_raster
from palimpsest.errors import PalimpsestError
from test_pdf_raster import pdf_bytes


_spec = importlib.util.spec_from_file_location('d2k_pdf_host', Path(__file__).resolve().parents[2] / 'tools/run_d2k_pdf.py')
host = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(host)
try:
    PINNED = importlib.metadata.version('pypdfium2') == '5.10.1' and importlib.metadata.version('Pillow') == '12.3.0'
except importlib.metadata.PackageNotFoundError:
    PINNED = False


class _PdfFixture:
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'original.pdf'
        self.raw = pdf_bytes()
        self.source.write_bytes(self.raw)
        self.owner = sha256(self.raw).hexdigest()

    def reject(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)


class D2kPdfHostTests(_PdfFixture, unittest.TestCase):
    def test_host_uses_only_pinned_offline_image_readonly_input_and_exact_output_mount(self):
        output = self.root / 'views'
        with patch.object(host, 'ROOT', self.root):
            command = host.docker_command(self.source, output, data_id=self.owner,
                byte_size=len(self.raw), page_numbers=[2, 1])
        self.assertIn(d2k_pdf.IMAGE, command)
        for flag, value in (('--network', 'none'), ('--pull', 'never'), ('--entrypoint', 'python'), ('--output', '/result')):
            self.assertEqual(command[command.index(flag) + 1], value)
        self.assertIn('--read-only', command)
        self.assertIn(f'{self.root.as_posix()}:/repo:ro', command)
        self.assertIn(f'{output.as_posix()}:/result', command)
        self.assertEqual(command[-4:], ['--page', '1', '--page', '2'])
        self.assertNotIn('--gpus', command)
        self.assertNotIn('mineru', command)
        self.assertNotIn('run_d2i.py', command)
        self.assertTrue(output.is_dir())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_host_rejects_wrong_identity_selection_existing_output_and_scope(self):
        with patch.object(host, 'ROOT', self.root):
            self.reject('original_pdf_changed', lambda: host.docker_command(self.source, self.root/'bad-hash',
                data_id='0'*64, byte_size=len(self.raw), page_numbers=[1]))
            self.reject('original_pdf_changed', lambda: host.docker_command(self.source, self.root/'bad-size',
                data_id=self.owner, byte_size=len(self.raw)+1, page_numbers=[1]))
            for pages in ([], [0], [1, 1], [True], ['1']):
                self.reject('invalid_pdf_page_selection', lambda: host.docker_command(self.source, self.root/'bad-pages',
                    data_id=self.owner, byte_size=len(self.raw), page_numbers=pages))
            output = self.root/'frozen'; output.mkdir(); (output/'retain.txt').write_text('Keep existing evidence.')
            self.reject('source_view_workspace_scope_required', lambda: host.docker_command(self.source, output,
                data_id=self.owner, byte_size=len(self.raw), page_numbers=[1]))
            self.reject('source_view_workspace_scope_required', lambda: host.docker_command(self.source, self.root.parent/'outside',
                data_id=self.owner, byte_size=len(self.raw), page_numbers=[1]))
        self.assertEqual((output/'retain.txt').read_text(), 'Keep existing evidence.')

    def test_unavailable_or_wrong_pdf_runtime_is_an_explicit_error_before_output(self):
        for failure in (ImportError('not installed'), ValueError('wrong pinned version')):
            with patch.object(pdf_raster, '_dependencies', side_effect=failure):
                self.reject('d2k_pdf_runtime_required', lambda: d2k_pdf.render_source(
                    self.source, self.root/'unavailable', self.owner, [1]))
        self.assertFalse((self.root/'unavailable').exists())


@unittest.skipUnless(PINNED, 'Native verification requires existing pinned PDFium 5.10.1/Pillow 12.3.0 image')
class D2kPdfNativeTests(_PdfFixture, unittest.TestCase):
    def render(self, pages=(1, 2), name='view'):
        output = self.root/name
        return output, d2k_pdf.render_source(self.source, output, self.owner, list(pages), expected_byte_size=len(self.raw))

    @staticmethod
    def write_manifest(output, manifest):
        (output/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_first_two_selected_pages_keep_exact_source_pixels_geometry_and_match_pure_pdf_views(self):
        from palimpsest import d2k
        boxes = [([0, 0, 210.37, 230.29], [10.13, 20.17, 200.31, 225.23]),
                 ([0, 0, 201.41, 227.19], [-10, -20, 300, 400]),
                 ([0, 0, 300, 400], [0, 0, 300, 400])]
        self.raw = pdf_bytes(boxes=boxes); self.source.write_bytes(self.raw); self.owner = sha256(self.raw).hexdigest()
        with patch.object(pdf_raster, '_raster', wraps=pdf_raster._raster) as renderer:
            output, manifest = self.render(pages=(2, 1))
        self.assertEqual(renderer.call_count, 4, 'Only two selected pages, each rendered and independently re-rendered')
        self.assertEqual(manifest['selected_page_numbers'], [1, 2])
        self.assertEqual(manifest['source']['page_count'], 3)
        self.assertEqual([page['page_index'] for page in manifest['pages']], [0, 1])
        self.assertEqual({path.name for path in output.iterdir()}, {'manifest.json', 'page-0001.png', 'page-0002.png'})
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertFalse(manifest['source_registration_verified'])
        self.assertFalse(manifest['actual_model_delivery'])
        for name in ('d2i_calls', 'information_created', 'model_calls', 'canonical_writes'):
            self.assertEqual(manifest[name], 0)
        self.assertEqual(d2k_pdf.verify_source(self.source, output, self.owner), manifest)
        for index, page in enumerate(manifest['pages']):
            view = {'kind': 'pdf_page', 'view_id': f'019947e2-1234-7000-8000-{index+1:012x}',
                'data_id': self.owner, 'original_byte_size': len(self.raw), 'page_index': page['page_index'],
                'page_count': 3, 'page_size': page['page_size'], 'image_sha256': page['png']['sha256'],
                'image_byte_size': page['png']['byte_size'], 'source_geometry': page['source_geometry'],
                'transforms': page['transforms'], 'renderer': manifest['renderer']}
            self.assertEqual(d2k.check_view(view), view)

    def test_tampered_pixels_fail_even_after_png_hash_and_size_are_forged_to_match(self):
        from PIL import Image
        output, manifest = self.render(pages=(1,))
        path = output/manifest['pages'][0]['png']['path']
        with Image.open(path) as opened:
            image = opened.copy()
        with image:
            pixel = image.getpixel((0, 0))
            image.putpixel((0, 0), ((pixel[0]+1) % 256, pixel[1], pixel[2]))
            image.save(path, format='PNG')
        manifest['pages'][0]['png'].update(sha256=sha256(path.read_bytes()).hexdigest(), byte_size=path.stat().st_size)
        self.write_manifest(output, manifest)
        self.reject('source_view_pixels_changed', lambda: d2k_pdf.verify_source(self.source, output, self.owner))

    def test_changed_registered_source_cannot_be_rebound_by_editing_manifest(self):
        output, manifest = self.render(pages=(1,))
        self.source.write_bytes(self.raw + b'\n% changed original')
        changed = self.source.read_bytes()
        manifest['source'].update(data_id=sha256(changed).hexdigest(), sha256=sha256(changed).hexdigest(), byte_size=len(changed))
        self.write_manifest(output, manifest)
        self.reject('original_pdf_changed', lambda: d2k_pdf.verify_source(self.source, output, self.owner))

    def test_geometry_selection_renderer_and_asset_paths_cannot_be_rebound(self):
        output, original = self.render()
        for mutation, code in (('geometry', 'source_view_asset_or_geometry_changed'),
                ('page', 'source_view_asset_or_geometry_changed'), ('order', 'source_view_page_selection_changed'),
                ('renderer', 'source_view_renderer_changed'), ('path', 'unsafe_source_view_asset')):
            manifest = deepcopy(original)
            if mutation == 'geometry': manifest['pages'][0]['transforms']['pixel_top_left_to_source_pdf_bottom_left'][0] += 0.1
            elif mutation == 'page': manifest['pages'][0]['page_index'] = 1
            elif mutation == 'order': manifest['pages'].reverse()
            elif mutation == 'renderer': manifest['renderer']['implementation_sha256']['pdf_raster.py'] = '0'*64
            else: manifest['pages'][0]['png']['path'] = '../page-0001.png'
            self.write_manifest(output, manifest)
            with self.subTest(mutation=mutation):
                self.reject(code, lambda: d2k_pdf.verify_source(self.source, output, self.owner))

    def test_existing_attempts_and_out_of_range_or_rotated_pages_fail_explicitly(self):
        output, _ = self.render(pages=(1,))
        frozen = (output/'manifest.json').read_bytes()
        self.reject('source_view_output_must_be_empty', lambda: d2k_pdf.render_source(self.source, output, self.owner, [1]))
        self.assertEqual((output/'manifest.json').read_bytes(), frozen)
        self.reject('invalid_pdf_page_selection', lambda: self.render(pages=(3,), name='range'))
        self.raw = pdf_bytes(rotation=90); self.source.write_bytes(self.raw); self.owner = sha256(self.raw).hexdigest()
        self.reject('unsupported_pdf_page_rotation', lambda: self.render(pages=(1,), name='rotated'))
        self.assertFalse((self.root/'rotated/manifest.json').exists())

    def test_symlink_asset_and_renderer_changed_during_render_cannot_publish_success(self):
        output, manifest = self.render(pages=(1,))
        png = output/manifest['pages'][0]['png']['path']; raw = png.read_bytes()
        other = self.root/'other.png'; other.write_bytes(raw); png.unlink(); png.symlink_to(other)
        self.reject('source_view_symlink_rejected', lambda: d2k_pdf.verify_source(self.source, output, self.owner))
        native_profile = d2k_pdf._profile
        calls = 0
        def changed_profile(*args):
            nonlocal calls
            calls += 1
            value = native_profile(*args)
            if calls > 1: value['implementation_sha256']['d2k_pdf.py'] = '0'*64
            return value
        with patch.object(d2k_pdf, '_profile', side_effect=changed_profile):
            self.reject('source_view_renderer_changed', lambda: self.render(pages=(1,), name='changed-renderer'))
        self.assertFalse((self.root/'changed-renderer/manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
