"""CLI/config unit checks; mocked services do not establish PG integration."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from palimpsest import cli
from palimpsest.config import load_config, load_dsn
from palimpsest.errors import PalimpsestError


REQUEST_ID = "01992d33-1020-7123-8123-123456789abc"
DATA_ID = "ab" * 32


class CLIUnitTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"PALIMPSEST_DATABASE_DSN": "postgresql://test.invalid/db"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def invoke(self, arguments, service=None):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(cli, "_service", return_value=service or Mock()) as factory:
            with patch("builtins.input", side_effect=AssertionError("CLI must not prompt")):
                with redirect_stdout(output), redirect_stderr(errors):
                    code = cli.main(arguments)
        return code, output.getvalue(), errors.getvalue(), factory

    def test_help_and_version_do_not_load_configuration_or_services(self):
        with patch.dict(os.environ, {}, clear=True):
            for arguments, key in ((["--json", "--help"], "help"), (["--version", "--json"], "version"),
                                   (["data", "import", "--help", "--json"], "help")):
                with self.subTest(arguments=arguments):
                    code, output, errors, factory = self.invoke(arguments)
                    result = json.loads(output)
                    self.assertEqual(code, 0)
                    self.assertEqual(result["command_status"], "succeeded")
                    self.assertIn(key, result["result"])
                    self.assertIsNone(result["job_status"])
                    self.assertEqual(errors, "")
                    factory.assert_not_called()

    def test_json_option_at_each_command_level(self):
        service = Mock()
        service.show.return_value = {"data_id": DATA_ID}
        for arguments in (["--json", "data", "show", DATA_ID], ["data", "--json", "show", DATA_ID],
                          ["data", "show", DATA_ID, "--json", "--non-interactive"]):
            with self.subTest(arguments=arguments):
                code, output, _, _ = self.invoke(arguments, service)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output)["result_refs"]["data_id"], DATA_ID)
        self.assertEqual(service.show.call_count, 3)

    def test_invalid_command_and_argument_values_are_not_echoed(self):
        secret = "postgresql://user:secret@host/private\x1b[2J"
        for arguments in (["compile", "--json"], ["data", "show", secret, "--json"],
                          ["requests", "recover", "invalid-uuid", "--json"],
                          ["--json", "--unknown=" + secret]):
            with self.subTest(arguments=arguments):
                code, output, errors, factory = self.invoke(arguments)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output)["command_status"], "failed")
                self.assertNotIn(secret, output + errors)
                factory.assert_not_called()

    def test_missing_config_is_machine_readable_and_doctor_reports_not_ready(self):
        with patch.dict(os.environ, {}, clear=True):
            for arguments, expected in ((["doctor", "--json"], 3), (["data", "show", DATA_ID, "--json"], 2)):
                with self.subTest(arguments=arguments):
                    code, output, _, factory = self.invoke(arguments)
                    result = json.loads(output)
                    self.assertEqual(code, expected)
                    self.assertEqual(result["error"]["code"], "database_not_configured")
                    factory.assert_not_called()
                    if expected == 3:
                        self.assertFalse(result["result"]["ready"])

    def test_import_early_request_notification_is_stderr_only(self):
        service = Mock()

        def register(path, **kwargs):
            self.assertEqual(path, Path("한국어 논문 'test'.pdf"))
            self.assertEqual(kwargs["request_id"], REQUEST_ID)
            self.assertEqual(kwargs["origin_uri"], "https://example.invalid/paper")
            kwargs["on_request_id"](REQUEST_ID)
            return {"request_id": REQUEST_ID, "data_id": DATA_ID, "state": "committed"}

        service.import_file.side_effect = register
        with patch('palimpsest.realm_registration.configured_service', return_value=service):
            code, output, errors, _ = self.invoke(
                ["data", "import", "한국어 논문 'test'.pdf", "--request-id", REQUEST_ID, "--media-type", "application/pdf",
                 "--origin-uri", "https://example.invalid/paper", "--realm-id", REQUEST_ID,
                 "--json", "--non-interactive"], Mock())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["result_refs"]["request_id"], REQUEST_ID)
        self.assertEqual(json.loads(errors)["event"], "request_started")
        self.assertEqual(json.loads(errors)["request_id"], REQUEST_ID)

    def test_request_and_verify_routes_preserve_service_arguments(self):
        for arguments, method, value in ((["requests", "show", REQUEST_ID], "request_status", REQUEST_ID),
                                         (["requests", "recover", REQUEST_ID], "recover", REQUEST_ID),
                                         (["data", "verify", DATA_ID], "verify", DATA_ID)):
            with self.subTest(method=method):
                service = Mock()
                getattr(service, method).return_value = {"request_id": REQUEST_ID}
                code, output, _, _ = self.invoke(arguments + ["--json"], service)
                self.assertEqual(code, 0)
                getattr(service, method).assert_called_once_with(value)
                self.assertEqual(json.loads(output)["schema_version"], 1)

    def test_error_statuses_and_reference_details_without_exception_body(self):
        private = "password=never-print SELECT * FROM secret; /private/source.pdf"
        for exit_code in range(2, 8):
            with self.subTest(exit_code=exit_code):
                service = Mock()
                service.show.side_effect = PalimpsestError("duplicate_data", private, exit_code,
                                                         {"data_id": DATA_ID, "sql": private, "path": private})
                code, output, errors, _ = self.invoke(["--json", "data", "show", DATA_ID], service)
                envelope = json.loads(output)
                self.assertEqual(code, exit_code)
                self.assertEqual(envelope["result_refs"], {"data_id": DATA_ID})
                self.assertEqual(envelope["error"]["details"], {"data_id": DATA_ID})
                self.assertNotIn(private, output + errors)

    def test_unexpected_exception_and_interrupt_are_safe(self):
        for exception, expected in ((RuntimeError("password=hidden\x1b[2J"), 4), (KeyboardInterrupt(), 130)):
            with self.subTest(exception=type(exception).__name__):
                service = Mock()
                service.show.side_effect = exception
                code, output, errors, _ = self.invoke(["data", "show", DATA_ID, "--json"], service)
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(output)["command_status"], "failed")
                self.assertNotIn("hidden", output + errors)
                self.assertNotIn("Traceback", output + errors)

    def test_doctor_parser_warning_does_not_block_t02_ready(self):
        service = Mock()
        service.doctor.return_value = {"ready": True, "database": {"ready": True}, "artifact_store": {"ready": True},
                                       "parser": {"name": "MinerU", "ready": False, "status": "not_configured"},
                                       "warnings": ["MinerU 미설정"]}
        with patch.object(cli, "_migrate") as migrate:
            code, output, errors, _ = self.invoke(["doctor", "--json"], service)
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["result"]["ready"])
        self.assertEqual(json.loads(errors)["warning"], "MinerU 미설정")
        migrate.assert_not_called()
        service.doctor.assert_called_once_with()
        service.import_file.assert_not_called()

    def test_doctor_unready_retains_diagnostic_result(self):
        service = Mock()
        service.doctor.return_value = {"ready": False, "database": {"ready": False}, "warnings": []}
        code, output, _, _ = self.invoke(["doctor", "--json"], service)
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(output)["result"]["database"]["ready"])

    def test_migration_uses_only_explicit_admin_configuration(self):
        with patch.dict(os.environ, {"PALIMPSEST_ADMIN_DSN": "admin-dsn"}, clear=True):
            with patch.object(cli, "_migrate", return_value={"schema_version": 1}) as migrate:
                code, output, _, factory = self.invoke(["db", "migrate", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["result"]["schema_version"], 1)
        migrate.assert_called_once_with("admin-dsn")
        factory.assert_not_called()

    def test_terminal_controls_escape_and_round_trip_in_machine_and_human_output(self):
        original = "논문\x1b[2J\x9b31m\u202ereversed\U000e0001name"
        service = Mock()
        service.show.return_value = {"original_name": original}
        for flags in ([], ["--json"]):
            with self.subTest(flags=flags):
                code, output, _, _ = self.invoke(["data", "show", DATA_ID] + flags, service)
                self.assertEqual(code, 0)
                for char in ("\x1b", "\x9b", "\u202e", "\U000e0001"):
                    self.assertNotIn(char, output)
                decoded = json.loads(output)
                self.assertEqual((decoded["result"] if flags else decoded)["original_name"], original)


class ConfigUnitTests(unittest.TestCase):
    def test_explicit_secret_file_defaults_and_safe_repr(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "dsn.secret"
            secret.write_text("postgresql://user:do-not-print@host/database\n", encoding="utf-8")
            with patch.dict(os.environ, {"PALIMPSEST_DATABASE_DSN_FILE": str(secret)}, clear=True):
                config = load_config()
            self.assertEqual(config.database_dsn, "postgresql://user:do-not-print@host/database")
            self.assertEqual(config.actor_ref, "local")
            self.assertEqual(config.artifact_root, Path("/var/lib/palimpsest/artifacts"))
            self.assertNotIn("do-not-print", repr(config))

    def test_ambiguous_empty_unreadable_and_oversize_config_fail_without_echo(self):
        cases = ({"PALIMPSEST_DATABASE_DSN": "secret", "PALIMPSEST_DATABASE_DSN_FILE": "private-file"},
                 {"PALIMPSEST_DATABASE_DSN": " "}, {"PALIMPSEST_DATABASE_DSN_FILE": "private-missing-file"},
                 {"PALIMPSEST_DATABASE_DSN": "secret" * 3000})
        for environment in cases:
            with self.subTest(environment_keys=list(environment)):
                with patch.dict(os.environ, environment, clear=True):
                    with self.assertRaises(PalimpsestError) as caught:
                        load_dsn()
                self.assertEqual(caught.exception.exit_code, 2)
                self.assertNotIn("private-missing-file", str(caught.exception))
                self.assertNotIn("secretsecret", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
