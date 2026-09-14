"""Wiki CLI state forwarding with a mocked Runtime; no storage or model calls."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from palimpsest import cli


class PaperWikiCliTests(unittest.TestCase):
    def stage(self, initial_state, expected_state):
        with TemporaryDirectory(prefix='palimpsest-wiki-cli-') as directory:
            response_path = Path(directory) / 'response.json'
            exchange = {'response': {'items': ['원문 표현']},
                        'receipt': {'provider_ref': 'synthetic-only', 'output_sha256': 'a' * 64}}
            response_path.write_text(json.dumps(exchange, ensure_ascii=False), encoding='utf-8')
            before = response_path.read_bytes()
            identifier = '019947e2-1234-7000-8000-000000000001'
            args = SimpleNamespace(action='stage', directory=Path(directory) / 'wiki',
                                   request_id=identifier, response=response_path)
            config = SimpleNamespace(database_dsn='postgresql://synthetic.invalid/unused',
                                     artifact_root=Path(directory) / 'artifacts')
            arguments = vars(args).copy()
            runtime = Mock()
            state = initial_state
            def stage(request_id, payload):
                nonlocal state
                if state == 'prepared':
                    state = 'proposed'
                return {'proposal': {'items': [{}, {}], 'topics': [{}]}}
            runtime.stage.side_effect = stage
            runtime.show.side_effect = lambda request_id: {'state': state}
            module = ModuleType('palimpsest.paper_wiki_runtime')
            constructor = module.PaperWikiRuntime = Mock(return_value=runtime)
            with patch.dict('sys.modules', {'palimpsest.paper_wiki_runtime': module}):
                result = cli._wiki(args, config)
            constructor.assert_called_once_with(config.database_dsn, config.artifact_root, args.directory)
            self.assertEqual(runtime.mock_calls, [call.stage(identifier, exchange), call.show(identifier)])
            self.assertEqual(result, {'request_id': identifier, 'state': expected_state, 'items': 2, 'topics': 1})
            self.assertEqual(vars(args), arguments)
            self.assertEqual(response_path.read_bytes(), before)

    def test_compiled_generator_replay_reports_compiled(self):
        self.stage('compiled', 'compiled')

    def test_initial_stage_reports_the_new_proposed_state(self):
        self.stage('prepared', 'proposed')


if __name__ == '__main__':
    unittest.main()
