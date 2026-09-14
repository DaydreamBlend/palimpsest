"""Mocked CLI boundary checks; these do not establish live model correctness."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from palimpsest.codex_provider import CodexProvider
from palimpsest.errors import PalimpsestError


THREAD = "01992d33-1020-7123-8123-123456789abc"
SCHEMA = {"type": "object", "properties": {"accepted": {"type": "boolean"}},
          "required": ["accepted"], "additionalProperties": False}


def events(*extra, answer='{"accepted":true}', complete=True):
    values = [{"type": "thread.started", "thread_id": THREAD}, *extra,
              {"type": "item.completed", "item": {"type": "agent_message", "text": answer}}]
    if complete:
        values.append({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 3}})
    return "\n".join(json.dumps(value) for value in values)


class CodexProviderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        self.provider = CodexProvider("codex.exe", timeout_seconds=17)

    def invoke(self, stream=None, **kwargs):
        outcomes = [subprocess.CompletedProcess([], 0, "codex-cli 0.153.4\n"),
                    subprocess.CompletedProcess([], 0, stream if stream is not None else events())]
        with patch("palimpsest.codex_provider.subprocess.run", side_effect=outcomes) as run:
            result = self.provider.generate(prompt="validate evidence", schema=SCHEMA,
                                            cwd=self.workspace, **kwargs)
        return result, run

    def test_isolated_oauth_call_uses_stdin_pinned_model_and_cleans_schema(self):
        image = self.workspace / "source image.png"
        image.write_bytes(b"synthetic attachment; subprocess is mocked")
        prompt = "Untrusted document with 'quotes' and $(commands)\n한글"
        observations = []

        def execute(arguments, **options):
            observations.append((arguments, options))
            if arguments[-1] == "--version":
                return subprocess.CompletedProcess(arguments, 0, "codex-cli 0.153.4\n")
            schema_path = Path(arguments[arguments.index("--output-schema") + 1])
            self.assertEqual(json.loads(schema_path.read_text(encoding="utf-8")), SCHEMA)
            return subprocess.CompletedProcess(arguments, 0, events())

        with patch.dict(os.environ, {"CODEX_HOME": "/existing/login", "PATH": "/bin",
                                    "OPENAI_API_KEY": "secret", "CODEX_API_KEY": "secret",
                                    "OPENAI_BASE_URL": "https://unexpected.invalid",
                                    "PALIMPSEST_DATABASE_DSN": "private"}, clear=True):
            with patch("palimpsest.codex_provider.subprocess.run", side_effect=execute):
                result = self.provider.generate(prompt=prompt, schema=SCHEMA, images=[image], cwd=self.workspace)
        args, options = observations[1]
        self.assertEqual(options["input"], prompt)
        self.assertNotIn(prompt, args)
        self.assertFalse(options["shell"])
        self.assertEqual(options["stderr"], subprocess.DEVNULL)
        self.assertEqual(options["env"], {"CODEX_HOME": "/existing/login", "PATH": "/bin"})
        self.assertEqual(options["timeout"], 17)
        self.assertEqual(args[args.index("--model") + 1], "gpt-5.6-terra")
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        self.assertIn('model_reasoning_effort="medium"', args)
        self.assertIn('forced_login_method="chatgpt"', args)
        self.assertIn('approval_policy="never"', args)
        for flag in ("--strict-config", "--ignore-user-config", "--ephemeral", "--json"):
            self.assertIn(flag, args)
        for setting in ('web_search="disabled"', 'history.persistence="none"', "project_doc_max_bytes=0"):
            self.assertIn(setting, args)
        disabled = {args[index + 1] for index, value in enumerate(args) if value == "--disable"}
        self.assertTrue({"shell_tool", "unified_exec", "apps", "plugins", "multi_agent", "hooks",
                         "browser_use", "computer_use", "image_generation", "view_image"} <= disabled)
        self.assertIn("skip_host_skill_discovery", args)
        self.assertFalse(any("bypass" in argument or argument == "--ignore-rules" for argument in args))
        self.assertFalse(Path(options["cwd"]).exists())
        self.assertTrue(image.exists())
        self.assertEqual(result.output, {"accepted": True})
        self.assertEqual(result.thread_ref, THREAD)
        self.assertEqual(result.profile["auth"], "chatgpt_oauth")
        self.assertEqual(result.profile["cli_version"], "0.153.4")

    def test_reasoning_and_unexpected_usage_are_not_returned(self):
        stream = events({"type": "item.completed", "item": {"type": "reasoning", "text": "PRIVATE_REASONING"}})
        stream = stream.replace('"output_tokens": 3', '"output_tokens": 3, "secret": "PRIVATE", "cached_input_tokens": true')
        result, _ = self.invoke(stream)
        self.assertEqual(result.usage, {"input_tokens": 12, "output_tokens": 3})
        self.assertNotIn("PRIVATE", repr(result))

    def test_nonfatal_cli_diagnostic_requires_a_completed_turn_and_json_answer(self):
        warning = {"type": "item.completed", "item": {"type": "error", "message": "PRIVATE_DIAGNOSTIC"}}
        result, _ = self.invoke(events(warning))
        self.assertEqual(result.output, {"accepted": True})
        self.assertEqual(result.profile["nonfatal_diagnostic_count"], 1)
        self.assertNotIn("PRIVATE", repr(result))
        with self.assertRaises(PalimpsestError):
            self.invoke(events(warning, complete=False))

    def test_calls_do_not_resume_generator_context_in_validator(self):
        outcomes = [subprocess.CompletedProcess([], 0, "codex-cli 0.153.4"),
                    subprocess.CompletedProcess([], 0, events())] * 2
        with patch("palimpsest.codex_provider.subprocess.run", side_effect=outcomes) as run:
            self.provider.generate(prompt="generator", schema=SCHEMA, cwd=self.workspace)
            self.provider.generate(prompt="validator", schema=SCHEMA, cwd=self.workspace)
        first, second = run.call_args_list[1], run.call_args_list[3]
        self.assertNotEqual(first.kwargs["cwd"], second.kwargs["cwd"])
        self.assertNotIn("resume", second.args[0])
        self.assertNotIn(THREAD, second.args[0])

    def test_incomplete_malformed_or_nonobject_results_fail_closed(self):
        for stream in (events(complete=False), events(answer="[]"), events(answer='{"x":NaN}'),
                       events(answer="```json\n{}\n```"), "not JSON", "[]", events().replace(THREAD, "private/path")):
            with self.subTest(stream=stream):
                with self.assertRaises(PalimpsestError) as error:
                    self.invoke(stream)
                self.assertEqual(error.exception.code, "codex_output_invalid")

    def test_provider_failure_and_tool_activity_never_become_success(self):
        for event, expected in (({"type": "turn.failed", "error": {"message": "PRIVATE"}}, "codex_execution_failed"),
                                ({"type": "error", "message": "PRIVATE"}, "codex_execution_failed"),
                                ({"type": "item.started", "item": {"type": "command_execution", "command": "PRIVATE"}}, "codex_unexpected_tool"),
                                ({"type": "item.completed", "item": {"type": "mcp_tool_call"}}, "codex_unexpected_tool")):
            with self.subTest(event=event):
                with self.assertRaises(PalimpsestError) as error:
                    self.invoke(events(event))
                self.assertEqual(error.exception.code, expected)
                self.assertNotIn("PRIVATE", str(error.exception))

    def test_execution_errors_do_not_leak_stderr_command_or_document(self):
        for failure, expected in ((FileNotFoundError("PRIVATE"), "codex_unavailable"),
                                  (subprocess.TimeoutExpired("PRIVATE", 17, output="PRIVATE", stderr="PRIVATE"), "codex_timeout"),
                                  (subprocess.CompletedProcess([], 1, "PRIVATE", "PRIVATE"), "codex_execution_failed")):
            with self.subTest(failure=failure):
                values = [subprocess.CompletedProcess([], 0, "codex-cli 0.153.4"), failure]
                with patch("palimpsest.codex_provider.subprocess.run", side_effect=values):
                    with self.assertRaises(PalimpsestError) as error:
                        self.provider.generate(prompt="PRIVATE", schema=SCHEMA, cwd=self.workspace)
                self.assertEqual(error.exception.code, expected)
                self.assertNotIn("PRIVATE", str(error.exception))
                self.assertFalse(list(self.workspace.iterdir()))

    def failure(self, stream, *, exit_code=0):
        values = [subprocess.CompletedProcess([], 0, "codex-cli 0.153.4"),
                  subprocess.CompletedProcess([], exit_code, stream, "PRIVATE_STDERR sk-private")]
        with patch("palimpsest.codex_provider.subprocess.run", side_effect=values):
            with self.assertRaises(PalimpsestError) as caught:
                self.provider.generate(prompt="PRIVATE_SOURCE", schema=SCHEMA, cwd=self.workspace)
        error = caught.exception
        self.assertNotIn("PRIVATE", str(error))
        self.assertNotIn("PRIVATE", json.dumps(error.details))
        self.assertNotIn("sk-private", json.dumps(error.details))
        self.assertLessEqual(set(error.details), {"category", "thread_ref", "usage", "event_counts",
                                                "completion_seen", "final_json_object_seen"})
        return error

    def test_error_diagnostics_are_categories_only_even_with_auth_keys_in_remote_text(self):
        cases = {
            "context_limit": {"code": "context_length_exceeded", "message": "PRIVATE text OPENAI_API_KEY=sk-private"},
            "rate_limit": {"message": "Rate limit reached. PRIVATE access_token=sk-private"},
            "usage_limit": {"code": "insufficient_quota", "message": "PRIVATE refresh_token=sk-private"},
            "authentication": {"message": "Refresh token expired. PRIVATE auth.json sk-private"},
            "model_access": {"code": "model_not_found", "message": "PRIVATE model config sk-private"},
            "structured_output_schema": {"message": "Invalid schema for response_format. PRIVATE_SCHEMA sk-private"},
            "transport": {"message": "Error sending request: connection reset. PRIVATE_URL sk-private"},
            "unknown": {"message": "PRIVATE generic failure sk-private"},
        }
        for category, remote_error in cases.items():
            with self.subTest(category=category):
                failure = self.failure(events({"type": "turn.failed", "error": remote_error}))
                self.assertEqual(failure.code, "codex_execution_failed")
                self.assertEqual({key:failure.details[key] for key in ('category','thread_ref','usage')},
                                 {"category": category, "thread_ref": THREAD,
                                  "usage": {"input_tokens": 12, "output_tokens": 3}})
                self.assertEqual(failure.details['event_counts']['turn.failed'], 1)
                self.assertIs(failure.details['completion_seen'], True)

    def test_nonzero_json_event_output_is_classified_but_final_text_is_discarded(self):
        stream = events({"type": "error", "message": "This input exceeds the context window. PRIVATE_SOURCE"},
                        answer='{"PRIVATE_ANSWER":"sk-private"}')
        failure = self.failure(stream, exit_code=1)
        self.assertEqual(failure.details['category'], 'context_limit')
        self.assertEqual(failure.details['thread_ref'], THREAD)
        self.assertNotIn('output', failure.details)

    def test_nonzero_plain_output_or_source_text_does_not_become_a_diagnosis(self):
        for stream in ('Rate limit PRIVATE plain non-event output',
                       events(answer='{"PRIVATE_ANSWER":"context_length_exceeded rate_limit sk-private"}'),
                       events({"type": "item.completed", "item": {"type": "reasoning", "text": "PRIVATE_RATE_LIMIT"}})):
            with self.subTest(stream=stream):
                self.assertEqual(self.failure(stream, exit_code=1).details['category'], 'unknown')

    def test_failure_metadata_keeps_only_valid_uuid_and_nonnegative_integer_usage(self):
        stream = '\n'.join(json.dumps(event) for event in [
            {'type': 'thread.started', 'thread_id': 'PRIVATE/path'},
            {'type': 'turn.failed', 'error': {'code': 'rate_limit_exceeded', 'message': 'PRIVATE'},
             'usage': {'input_tokens': 7, 'cached_input_tokens': True, 'output_tokens': -1,
                       'reasoning_output_tokens': 2.5, 'access_token': 'sk-private'}}])
        failure = self.failure(stream, exit_code=1)
        self.assertEqual(failure.details['category'], 'rate_limit')
        self.assertEqual(failure.details['usage'], {'input_tokens': 7})
        self.assertNotIn('thread_ref', failure.details)

    def test_timeout_and_unavailable_have_precise_codes_and_transport_category(self):
        captured = events({'type': 'error', 'message': 'usage limit PRIVATE'}, complete=False).encode()
        for cause, code in ((subprocess.TimeoutExpired('PRIVATE', 17, output=captured, stderr='sk-private'), 'codex_timeout'),
                            (FileNotFoundError('PRIVATE'), 'codex_unavailable')):
            with self.subTest(code=code):
                values = [subprocess.CompletedProcess([], 0, 'codex-cli 0.153.4'), cause]
                with patch('palimpsest.codex_provider.subprocess.run', side_effect=values):
                    with self.assertRaises(PalimpsestError) as caught:
                        self.provider.generate(prompt='PRIVATE', schema=SCHEMA, cwd=self.workspace)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.details['category'], 'transport')
                self.assertNotIn('PRIVATE', json.dumps(caught.exception.details))
                if code == 'codex_timeout':
                    self.assertEqual(caught.exception.details['thread_ref'], THREAD)

    def test_fatal_unknown_is_not_guessed_from_nonfatal_startup_warning(self):
        stream = events({'type': 'item.completed', 'item': {'type': 'error', 'message': 'rate limit PRIVATE warning'}},
                        {'type': 'turn.failed', 'error': {'message': 'PRIVATE unspecified fatal'}})
        self.assertEqual(self.failure(stream).details['category'], 'unknown')

    def test_explicit_error_code_has_priority_over_quoted_message_words(self):
        stream = events({'type': 'turn.failed', 'error': {'code': 'invalid_json_schema',
            'message': 'PRIVATE schema contains fields named context_length_exceeded and authentication_error'}})
        self.assertEqual(self.failure(stream).details['category'], 'structured_output_schema')
        stream = events({'type': 'turn.failed', 'error': {'message': 'PRIVATE upstream failure',
            'codex_error_info': {'ContextWindowExceeded': {'authorization': 'sk-private'}}}})
        self.assertEqual(self.failure(stream).details['category'], 'context_limit')

    def test_recovered_transport_error_requires_a_later_completed_json_turn(self):
        for message in ('Reconnecting... 2/5 (PRIVATE transport detail)',
                        'Reconnecting... waiting for network',
                        'Stream disconnected before completion: error sending request PRIVATE'):
            with self.subTest(message=message):
                result, _ = self.invoke(events({'type':'error','message':message}))
                self.assertEqual(result.output, {'accepted':True})
                self.assertEqual(result.profile['recovered_transport_error_count'], 1)
                self.assertNotIn('PRIVATE', repr(result))

    def test_recovery_uses_fresh_final_message_and_keeps_diagnostic_counts_separate(self):
        stream = events(
            {'type':'item.completed','item':{'type':'agent_message','text':'{"accepted":false}'}},
            {'type':'error','message':'Reconnecting... 1/5 (PRIVATE)'},
            {'type':'item.completed','item':{'type':'error','message':'PRIVATE startup warning'}},
            {'type':'error','message':'Stream disconnected before completion PRIVATE'},
        )
        result, _ = self.invoke(stream)
        self.assertEqual(result.output, {'accepted':True})
        self.assertEqual(result.profile['recovered_transport_error_count'], 2)
        self.assertEqual(result.profile['nonfatal_diagnostic_count'], 1)

    def test_retry_followed_by_failure_nonzero_or_missing_final_still_fails(self):
        reconnect = {'type':'error','message':'Reconnecting... 1/5 (PRIVATE)'}
        for stream, exit_code in (
            (events(reconnect, {'type':'turn.failed','error':{'message':'PRIVATE fatal'}}), 0),
            (events(reconnect), 1),
            (events(reconnect, complete=False), 0),
            (events(reconnect, answer='PRIVATE non-JSON answer'), 0),
            (events() + '\n' + json.dumps(reconnect), 0),
            (events(reconnect, {'type':'error','message':'PRIVATE unknown fatal'}), 0),
            (events(reconnect, {'type':'item.completed','item':{'type':'command_execution','command':'PRIVATE'}}), 0),
        ):
            with self.subTest(exit_code=exit_code, stream=stream):
                self.failure(stream, exit_code=exit_code)

    def test_json_before_retry_without_new_message_cannot_be_reused_as_success(self):
        stream = '\n'.join(json.dumps(event) for event in [
            {'type':'thread.started','thread_id':THREAD},
            {'type':'item.completed','item':{'type':'agent_message','text':'{"accepted":true}'}},
            {'type':'error','message':'Reconnecting... 1/5 (PRIVATE)'},
            {'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':3}},
        ])
        failure = self.failure(stream)
        self.assertEqual(failure.code, 'codex_output_invalid')
        self.assertIs(failure.details['completion_seen'], True)
        self.assertIs(failure.details['final_json_object_seen'], False)

    def test_safe_event_counts_never_include_unknown_names_or_response_content(self):
        stream = events({'type':'PRIVATE_EVENT','message':'sk-private'},
                        {'type':'error','message':'PRIVATE unknown fatal'}, answer='{"PRIVATE":"sk-private"}')
        failure = self.failure(stream)
        self.assertEqual(failure.details['event_counts']['other_event'], 1)
        self.assertEqual(failure.details['event_counts']['error'], 1)
        self.assertEqual(failure.details['event_counts']['item.agent_message.completed'], 1)
        self.assertIs(failure.details['final_json_object_seen'], True)
        self.assertTrue(all(type(value) is int and value >= 0 for value in failure.details['event_counts'].values()))

    def test_recoverable_notice_does_not_mask_a_later_unknown_fatal_category(self):
        stream = events({'type':'error','message':'Reconnecting... 1/5'},
                        {'type':'error','message':'PRIVATE unclassified terminal problem'})
        failure = self.failure(stream)
        self.assertEqual(failure.details['category'], 'unknown')
        self.assertEqual(failure.details['event_counts']['transport_error'], 1)

    def test_unsupported_cli_version_stops_before_model_call(self):
        with patch("palimpsest.codex_provider.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "codex-cli 0.999.0")) as run:
            with self.assertRaises(PalimpsestError) as error:
                self.provider.generate(prompt="test", schema=SCHEMA, cwd=self.workspace)
        self.assertEqual(error.exception.code, "codex_version_unsupported")
        self.assertEqual(run.call_count, 1)

    def test_invalid_local_input_stops_before_cli_call(self):
        with patch("palimpsest.codex_provider.subprocess.run") as run:
            with self.assertRaises(PalimpsestError) as error:
                self.provider.generate(prompt="test", schema=SCHEMA, cwd=self.workspace,
                                       images=[self.workspace / "missing.png"])
        self.assertEqual(error.exception.code, "codex_input_invalid")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
