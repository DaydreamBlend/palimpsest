"""Worker image/model selection contracts; no Docker, database, or inference."""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest.hybrid_profile import HYBRID_PARSER
from palimpsest.errors import PalimpsestError


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('hybrid_worker', ROOT / 'tools/run_d2i.py')
worker_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(worker_module)


class HybridWorkerTests(unittest.TestCase):
    def test_long_parse_has_no_deadline_and_cancellation_removes_its_container(self):
        with TemporaryDirectory() as temporary, patch.object(worker_module, 'ROOT', Path(temporary).resolve()):
            args = worker_module.parse_args(['--data-id', 'a' * 64, '--work-dir', str(Path(temporary) / 'work')])
            worker = worker_module.Worker(args)
            worker.job_id = 'test-job'
            worker.app = lambda *args, **kwargs: {'state': 'prepared', 'attempt': 1}
            worker.parser_command = lambda output, name: ['parser', name]
            with patch.object(worker_module, 'command', side_effect=KeyboardInterrupt) as parse, \
                    patch.object(worker_module.subprocess, 'run') as cleanup:
                with self.assertRaises(KeyboardInterrupt):
                    worker.continue_job()
                self.assertIsNone(parse.call_args.kwargs['timeout'])
                name = parse.call_args.args[0][1]
                cleanup.assert_called_once_with(['docker', 'rm', '--force', name], capture_output=True, timeout=30)

    def test_default_is_explicit_hybrid_and_launch_binds_both_readonly_model_stores(self):
        with TemporaryDirectory() as temporary, patch.object(worker_module, 'ROOT', Path(temporary).resolve()):
            root = Path(temporary).resolve()
            for name in ('src/palimpsest/mineru_adapter.py', 'src/palimpsest/information.py',
                         'src/palimpsest/d2i.py', 'src/palimpsest/source_units.py',
                         'src/palimpsest/compiler_runtime.py', 'src/palimpsest/figure_adapter.py',
                         'src/palimpsest/hybrid_profile.py',
                         'src/palimpsest/hybrid_receipt.py', 'src/palimpsest/pdf_raster.py',
                         'src/palimpsest/pdf_raster_adapter.py', 'src/palimpsest/dual_adapter.py',
                         'src/palimpsest/image_adapter.py',
                         'src/palimpsest/source_groups.py', 'src/palimpsest/section_projection.py',
                         'src/palimpsest/figure_references.py',
                         'src/palimpsest/transcription_selection.py',
                         'src/palimpsest/figure_coverage.py', 'deploy/mineru/run_parser.py',
                         'deploy/mineru-hybrid/run_parser.py'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'Synthetic implementation hash fixture; not executed')
            (root/'src/palimpsest/pdf_raster.py').write_bytes((ROOT/'src/palimpsest/pdf_raster.py').read_bytes())
            args = worker_module.parse_args(['--data-id','a' * 64, '--work-dir',str(root / 'work')])
            self.assertEqual('mineru-hybrid', args.parser)
            self.assertEqual('palimpsest-mineru-hybrid:3.4.5-pro2605', args.parser_image)
            self.assertEqual('GPU-ae1e4ffa-2dba-7ba3-f9f7-1bae0ab26f57', args.gpu)
            worker = worker_module.Worker(args)
            responses = [HYBRID_PARSER['image_digest'] + '\n',
                         json.dumps({'manifest':{}, 'sha256':HYBRID_PARSER['models_manifest_sha256']}),
                         json.dumps({'manifest':{}, 'sha256':HYBRID_PARSER['pipeline_models_manifest_sha256']})]
            with patch.object(worker_module, 'command', side_effect=responses) as command:
                profile = worker.profile()
            for call in command.call_args_list[1:]:
                self.assertIn(HYBRID_PARSER['image_digest'], call.args[0])
                self.assertNotIn(args.parser_image, call.args[0])
            self.assertEqual('mineru-hybrid-image200-v1', profile['parser']['adapter_version'])
            self.assertEqual('image200', profile['parser']['transcription_mode'])
            self.assertEqual('source-groups-v1', profile['transformation']['algorithm'])
            self.assertEqual('blocks', worker_module.parse_args([
                '--data-id', 'a' * 64, '--work-dir', str(root / 'legacy'),
                '--information-layout', 'blocks']).information_layout)
            launch = worker.parser_command(worker.work / 'parser' / 'attempt-1', 'fixture-parser')
            self.assertIn(args.models_volume + ':/models:ro', launch)
            self.assertIn(args.pipeline_models_volume + ':/pipeline-models:ro', launch)
            self.assertIn(str(root/'src').replace('\\','/') + ':/runtime:ro', launch)
            self.assertIn('PYTHONPATH=/runtime', launch)
            self.assertIn(str(root / 'deploy/mineru-hybrid/run_parser.py').replace('\\','/') + ':/run_parser.py:ro', launch)
            self.assertEqual(HYBRID_PARSER['image_digest'], launch[launch.index('--entrypoint') + 2])
            self.assertEqual(HYBRID_PARSER['image_digest'], launch[launch.index('--image-digest') + 1])
            self.assertEqual('none', launch[launch.index('--network') + 1])
            self.assertEqual('/work/profile.json', launch[launch.index('--profile') + 1])
            with patch.object(worker_module, 'command', return_value='sha256:' + '0' * 64), self.assertRaises(PalimpsestError):
                worker.profile()
            changed_models = list(responses)
            changed_models[2] = json.dumps({'manifest':{}, 'sha256':'0' * 64})
            with patch.object(worker_module, 'command', side_effect=changed_models), self.assertRaises(PalimpsestError):
                worker.profile()

    def test_previous_parsers_are_explicit_options_and_legacy_repair_cannot_leak_to_hybrid(self):
        base = ['--data-id','a' * 64, '--work-dir',str(ROOT / 'output/hybrid-worker-test-not-created')]
        for parser, image in [('mineru','palimpsest-mineru:3.4.5'),
                              ('mineru-hybrid-dual','palimpsest-mineru-hybrid:3.4.5-pro2605'),
                              ('mineru-hybrid-native','palimpsest-mineru-hybrid:3.4.5-pro2605'),
                              ('paddleocr-vl','palimpsest-paddleocr:3.7.0-vl1.6')]:
            args = worker_module.parse_args([*base, '--parser',parser])
            self.assertEqual(parser, args.parser)
            self.assertEqual(image, args.parser_image)
        with TemporaryDirectory() as temporary, patch.object(worker_module, 'ROOT', Path(temporary).resolve()):
            args = worker_module.parse_args(['--data-id','a' * 64, '--work-dir',str(Path(temporary) / 'work'),
                                            '--reuse-parser-job','old-job', '--figure-inventory','old.json'])
            with self.assertRaises(PalimpsestError) as caught:
                worker_module.Worker(args)
            self.assertEqual('unsupported_figure_repair', caught.exception.code)


if __name__ == '__main__':
    unittest.main()
