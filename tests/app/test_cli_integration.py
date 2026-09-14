"""Real headless CLI subprocesses against the explicitly provisioned test DB."""

from hashlib import sha256
import json
from importlib.metadata import version
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4


@unittest.skipUnless(os.environ.get("PALIMPSEST_TEST_DSN") and os.environ.get('PALIMPSEST_REALM_TEST_DSN'),
                     "Requires disposable PG18 source and Realm catalog DBs")
class CliIntegrationTests(unittest.TestCase):
    def test_headless_registration_and_request_workflow(self):
        from palimpsest.canonical_store import PostgresRepository
        from palimpsest.realms import RealmCatalog
        repository = PostgresRepository(os.environ['PALIMPSEST_TEST_DSN'])
        realm = RealmCatalog(os.environ['PALIMPSEST_REALM_TEST_DSN']).create(
            'CLI fixture', '', 'local', 'Synthetic registration check', repository.allocate_id())
        with tempfile.TemporaryDirectory(prefix="palimpsest-cli-") as directory:
            base = Path(directory)
            root = base / "artifacts"
            root.mkdir()
            source = base / "논문 '원본' \x1b[31m.txt"
            payload = b"Palimpsest CLI fixture\n" + uuid4().bytes
            source.write_bytes(payload)
            environment = dict(os.environ)
            environment.pop("PALIMPSEST_DATABASE_DSN_FILE", None)
            environment.pop("DISPLAY", None)
            environment.pop("WAYLAND_DISPLAY", None)
            environment.update(PALIMPSEST_DATABASE_DSN=os.environ["PALIMPSEST_TEST_DSN"],
                               PALIMPSEST_ARTIFACT_ROOT=str(root), PALIMPSEST_ACTOR="local",
                               PALIMPSEST_STORE_ID=repository.allocate_id(),
                               PALIMPSEST_REALM_DSN=os.environ['PALIMPSEST_REALM_TEST_DSN'])
            environment.pop('PALIMPSEST_REALM_DSN_FILE', None)

            def call(*arguments, expected=0):
                process = subprocess.run(
                    [sys.executable, "-m", "palimpsest", *arguments, "--json", "--non-interactive"],
                    input="", capture_output=True, text=True, encoding="utf-8",
                    timeout=20, env=environment,
                )
                self.assertEqual(process.returncode, expected, process.stdout)
                self.assertEqual(len(process.stdout.splitlines()), 1)
                self.assertNotIn("\x1b", process.stdout + process.stderr)
                self.assertNotIn(environment["PALIMPSEST_DATABASE_DSN"], process.stdout + process.stderr)
                result = json.loads(process.stdout)
                self.assertEqual(result["schema_version"], 1)
                self.assertEqual(result["command_status"], "succeeded" if expected == 0 else "failed")
                self.assertIsNone(result["job_status"])
                for line in process.stderr.splitlines():
                    event = json.loads(line)
                    self.assertTrue("event" in event or "warning" in event)
                return result

            self.assertIn("data", call("--help")["result"]["help"])
            self.assertEqual(call("--version")["result"]["version"], version("palimpsest"))
            doctor = call("doctor")["result"]
            self.assertTrue(doctor["ready"])
            self.assertEqual(doctor["parser"]["status"], "not_probed")
            missing = call('data', 'import', str(source), expected=2)
            self.assertEqual(missing['error']['code'], 'realm_required')
            imported = call("data", "import", str(source), '--realm-id', realm['realm_id'])["result"]
            data_id, request_id = imported["data_id"], imported["request_id"]
            self.assertEqual(data_id, sha256(payload).hexdigest())
            shown = call("data", "show", data_id)["result"]
            self.assertEqual(shown["original_name"], source.name)
            self.assertEqual(len(shown["acquisitions"]), 1)
            self.assertTrue(call("data", "verify", data_id)["result"]["verified"])
            duplicate = call("data", "import", str(source), '--realm-id', realm['realm_id'], expected=6)
            self.assertEqual(duplicate["error"]["code"], "duplicate_data")
            self.assertEqual(duplicate["result_refs"]["data_id"], data_id)
            replay = call("data", "import", str(source), "--request-id", request_id,
                          '--realm-id', realm['realm_id'])["result"]
            self.assertTrue(replay["replayed"])
            self.assertEqual(replay["acquisition_id"], imported["acquisition_id"])
            self.assertEqual(call("requests", "show", request_id)["result"]["state"], "committed")
            self.assertTrue(call("requests", "recover", request_id)["result"]["replayed"])
            self.assertEqual(source.read_bytes(), payload)
