"""T03 persistence checks against an explicitly provisioned disposable PG18 DB.

Parser output and provider receipts are synthetic contract fixtures. No MinerU
or model is invoked, and passing this suite says nothing about semantic quality.
Each test imports unique fixture bytes into a private Artifact Store. This suite
does not reset, truncate, delete, or migrate database history. The caller owns
provisioning/disposal; PALIMPSEST_TEST_DSN must never identify a live database.
"""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from palimpsest.artifact_store import ArtifactStore
from palimpsest.canonical_store import MIGRATIONS, PostgresRepository, migration_source
from palimpsest.compiler_runtime import CompilerRuntime, digest
from palimpsest.errors import PalimpsestError
from palimpsest.service import DataService


@unittest.skipUnless(os.environ.get("PALIMPSEST_TEST_DSN"),
                     "Requires explicitly provisioned PALIMPSEST_TEST_DSN")
class InformationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["PALIMPSEST_TEST_DSN"]
        with psycopg.connect(cls.dsn) as conn:
            if int(conn.execute("SHOW server_version_num").fetchone()[0]) // 10000 != 18:
                raise RuntimeError("T03 integration profile requires PostgreSQL 18")
            if not conn.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone():
                raise RuntimeError("Provision pgvector before running T03 tests")
            if not conn.execute("SELECT 1 FROM compiler_runtime.schema_migrations WHERE version='0002_information'").fetchone():
                raise RuntimeError("Provision the reviewed T03 migration before testing")

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="palimpsest-t03-integration-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / "artifacts"
        self.repository = PostgresRepository(self.dsn)
        self.service = DataService(self.repository, ArtifactStore(self.root), actor_ref="local")
        self.data_id = self._import_fixture("source.pdf")
        self.runtime = CompilerRuntime(self.dsn, self.root)
        provider = {"provider": "codex_cli", "model": "gpt-5.6-terra",
                    "reasoning_effort": "medium", "auth": "chatgpt_oauth", "cli_version": "0.153.4"}
        self.profile = {
            "schema_version": "d2i-v1",
            "parser": {"provider": "mineru", "version": "3.4.5", "backend": "pipeline",
                       "image_digest": "sha256:" + "a" * 64, "models_manifest_sha256": "b" * 64},
            "generator": dict(provider), "validator": dict(provider),
            "policy": {"fixture": "synthetic_contract_test_no_model_calls",
                       "generator_prompt": "d2i-generator-v1", "validator_prompt": "d2i-validator-v2"},
        }
        self.directory = self.base / "synthetic-parser-output"
        (self.directory / "images").mkdir(parents=True)
        self.image_bytes = b"synthetic image integrity fixture; no image decoding or MinerU execution"
        (self.directory / "images/figure.png").write_bytes(self.image_bytes)
        text = {"type": "text", "bbox": [10, 20, 300, 60], "lines": [
            {"bbox": [10, 20, 300, 60], "spans": [{"type": "text", "content": "Fixture observation."}]}]}
        figure = {"type": "image", "bbox": [10, 100, 300, 400], "blocks": [
            {"type": "image_body", "bbox": [10, 100, 300, 350], "lines": [
                {"spans": [{"type": "image", "image_path": "figure.png"}]}]},
            {"type": "image_caption", "bbox": [10, 360, 300, 400], "lines": [
                {"spans": [{"type": "text", "content": "Synthetic figure caption."}]}]},
        ]}
        self.middle_path = self.directory / "fixture_middle.json"
        self.middle_path.write_text(json.dumps({"pdf_info": [
            {"page_idx": 0, "page_size": [600, 800], "para_blocks": [text, figure]}]}), encoding="utf-8")

    def _import_fixture(self, name):
        # Intentionally not a real PDF: registration verifies bytes, not parsing.
        source = self.base / name
        payload = b"%PDF-1.7\nSynthetic T03 persistence fixture\n" + uuid4().bytes
        source.write_bytes(payload)
        self.service.import_file(source, media_type="application/pdf")
        return sha256(payload).hexdigest()

    def _row(self, sql, params=()):
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            return conn.execute(sql, params).fetchone()

    def _assert_error(self, code, action):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(code, caught.exception.code)
        self.assertNotEqual(0, caught.exception.exit_code)

    def _prepared(self, generation=1):
        job = self.runtime.start(self.data_id, self.profile, generation)
        execution_id = job["execution_id"]
        self.runtime.attach_parser(execution_id, self.directory, self.middle_path.name, 1)
        return execution_id

    def _proposal(self, image=False):
        refs = ["/pdf_info/0/para_blocks/0"]
        if image:
            refs.append("/pdf_info/0/para_blocks/1")
        return {"kind": "image" if image else "text", "semantic_type": "figure" if image else "observation",
                "title": "Synthetic fixture", "content": "The synthetic fixture records an observation.",
                "block_ids": refs, "image_block_id": refs[-1] if image else None}

    def _receipt(self, role, output):
        parsed = self._row("""SELECT execution_id,bundle FROM compiler_runtime.parse_artifacts
            WHERE data_id=%s ORDER BY parse_artifact_id DESC LIMIT 1""", (self.data_id,))
        if role == "generator":
            proposals = output["proposals"]
        else:
            proposals = self.runtime.show(parsed["execution_id"], include_input=True)["proposals"]
        return {"profile": deepcopy(self.profile[role]), "thread_ref": "synthetic-" + role + "-" + uuid4().hex,
                "output_sha256": digest(output), "receipt_kind": "synthetic_contract_fixture",
                "source_bundle_sha256": digest(parsed["bundle"]), "proposal_set_sha256": digest(proposals),
                "prompt_version": self.profile["policy"][role + "_prompt"]}

    @staticmethod
    def _decisions(*verdicts):
        return [{"ordinal": ordinal, "verdict": verdict, "reason_codes": ["synthetic_fixture"],
                 "reason": "Synthetic persistence test decision, not a model assessment."}
                for ordinal, verdict in enumerate(verdicts)]

    def _proposed(self, *, image=False):
        execution_id = self._prepared()
        proposals = [self._proposal(image)]
        receipt = self._receipt("generator", {"proposals": proposals})
        self.runtime.propose(execution_id, proposals, receipt)
        return execution_id, proposals, receipt

    def _accept(self, execution_id):
        decisions = self._decisions("accepted")
        receipt = self._receipt("validator", {"decisions": decisions})
        return self.runtime.decide(execution_id, decisions, receipt), decisions, receipt

    def _counts(self, execution_id):
        return self._row("""SELECT
            (SELECT count(*) FROM compiler_runtime.records WHERE execution_id=%s) AS records,
            (SELECT count(*) FROM compiler_runtime.temporary_candidates c JOIN compiler_runtime.records r
                USING(record_id) WHERE r.execution_id=%s) AS candidates,
            (SELECT count(*) FROM canonical_store.information i JOIN compiler_runtime.records r
                ON r.record_id=i.origin_record_id WHERE r.execution_id=%s) AS information,
            (SELECT count(*) FROM canonical_store.information_groundings g JOIN canonical_store.information i
                USING(information_id) JOIN compiler_runtime.records r ON r.record_id=i.origin_record_id
                WHERE r.execution_id=%s) AS groundings,
            (SELECT count(*) FROM compiler_runtime.outbox o JOIN compiler_runtime.records r
                USING(record_id) WHERE r.execution_id=%s) AS outbox""", (execution_id,) * 5)

    def _parallel(self, action):
        barrier = Barrier(2)

        def invoke():
            runtime = CompilerRuntime(self.dsn, self.root)
            barrier.wait(timeout=15)
            return action(runtime)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(invoke) for _ in range(2)]
            return [future.result(timeout=30) for future in futures]

    def test_accepted_image_commits_snapshot_groundings_record_cleanup_and_outbox(self):
        execution_id, proposals, generator = self._proposed(image=True)
        result, _, validator = self._accept(execution_id)
        self.assertEqual("completed", result["state"])
        self.assertEqual({"records": 1, "candidates": 0, "information": 1, "groundings": 2, "outbox": 1},
                         self._counts(execution_id))
        job = self.runtime.show(execution_id, include_input=True)
        self.assertEqual(generator, job["generator_receipt"])
        self.assertEqual(validator, job["validator_receipt"])
        information = self.runtime.information(information_id=result["information_ids"][0])["information"][0]
        self.assertEqual(self.data_id, information["data_id"])
        self.assertEqual(proposals[0]["content"], information["content"])
        self.assertEqual("accepted", job["records"][0]["disposition"])
        self.assertEqual(information["origin_record_id"], job["records"][0]["record_id"])
        self.assertEqual(7, UUID(str(information["information_id"])).version)
        for grounding in information["groundings"]:
            block = next(b for b in job["parse"]["bundle"]["blocks"] if b["block_id"] == grounding["block_id"])
            for key in ("page_index", "bbox", "page_size", "raw_locator", "anchor_sha256"):
                self.assertEqual(block[key], grounding[key])
            self.assertEqual(job["parse"]["parse_artifact_id"], grounding["parse_artifact_id"])
        image = information["payload"]["images"][0]
        self.assertEqual(sha256(self.image_bytes).hexdigest(), image["sha256"])
        self.assertEqual(self.image_bytes, (self.root / image["artifact_path"]).read_bytes())
        outbox = self._row("SELECT * FROM compiler_runtime.outbox WHERE information_id=%s", (information["information_id"],))
        self.assertEqual(("i2k", "pending", information["origin_record_id"]),
                         (outbox["operation"], outbox["state"], outbox["record_id"]))

    def test_before_commit_failure_rolls_back_every_effect_then_retries(self):
        execution_id, _, _ = self._proposed()
        decisions = self._decisions("accepted")
        receipt = self._receipt("validator", {"decisions": decisions})

        def crash(checkpoint):
            self.assertEqual("before_commit", checkpoint)
            raise RuntimeError("injected pre-commit failure")

        with self.assertRaisesRegex(RuntimeError, "injected pre-commit failure"):
            self.runtime.decide(execution_id, decisions, receipt, checkpoint=crash)
        self.assertEqual({"records": 1, "candidates": 1, "information": 0, "groundings": 0, "outbox": 0},
                         self._counts(execution_id))
        job = self.runtime.show(execution_id)
        self.assertEqual("proposed", job["state"])
        self.assertIsNone(job["validator_receipt"])
        self.assertIsNone(job["records"][0]["disposition"])
        self.assertEqual(["prepared", "parsed", "proposed"], [event["state"] for event in job["events"]])
        self.assertEqual("completed", self.runtime.decide(execution_id, decisions, receipt)["state"])

    def _figure_repair_prepared(self, generation=2):
        full_image = b'Full graphical body fixture, distinct from the panel.'
        (self.directory / 'images/full-figure.png').write_bytes(full_image)
        inventory = {
            'schema_version':'figure-inventory-v1', 'data_id':self.data_id,
            'middle_sha256':sha256(self.middle_path.read_bytes()).hexdigest(),
            'extraction_scope':'figures_only', 'source':'reviewed_original_pdf_regions',
            'renderer':{'name':'synthetic_fixture_not_pdf_render'},
            'figures':[{'number':1,'page_index':0,'bbox':[10,100,300,350],
                        'member_block_ids':['/pdf_info/0/para_blocks/1'],
                        'caption_block_ids':['/pdf_info/0/para_blocks/1'],
                        'image':{'path':'images/full-figure.png','sha256':sha256(full_image).hexdigest(),
                                 'byte_size':len(full_image)}}]}
        inventory_path=self.directory/'palimpsest_figures.json'
        inventory_path.write_text(json.dumps(inventory),encoding='utf-8')
        self.profile['policy']['figure_inventory_sha256']=sha256(inventory_path.read_bytes()).hexdigest()
        return self._prepared(generation)

    @staticmethod
    def _figure_repair_proposal():
        return {'kind':'image','semantic_type':'figure','title':'Figure 1',
                'content':'The source figure presents the complete graphical body with its caption.',
                'image_block_id':'/figures/0',
                'block_ids':['/figures/0','/pdf_info/0/para_blocks/1']}

    def test_missing_required_figure_cannot_be_committed_as_zero_output(self):
        execution_id=self._figure_repair_prepared()
        receipt=self._receipt('generator',{'proposals':[]})
        self._assert_error('incomplete_figure_coverage',lambda:self.runtime.propose(execution_id,[],receipt))
        self.assertEqual('parsed',self.runtime.show(execution_id)['state'])
        self.assertEqual(0,self._counts(execution_id)['records'])

    def test_full_figure_repair_preserves_old_snapshot_and_commits_whole_image(self):
        old_job,_,_=self._proposed(image=True)
        old_result,_,_=self._accept(old_job)
        old_id=old_result['information_ids'][0]
        old_snapshot=self.runtime.information(information_id=old_id)
        execution_id=self._figure_repair_prepared()
        proposals=[self._figure_repair_proposal()]
        self.runtime.propose(execution_id,proposals,self._receipt('generator',{'proposals':proposals}))
        result,_,_=self._accept(execution_id)
        self.assertEqual('completed',result['state'])
        current=self.runtime.information(information_id=result['information_ids'][0])['information'][0]
        self.assertEqual(1,current['payload']['figure']['figure_number'])
        self.assertNotEqual(old_id,current['information_id'])
        self.assertEqual(old_snapshot,self.runtime.information(information_id=old_id))
        self.assertEqual(b'Full graphical body fixture, distinct from the panel.',
                         (self.root/current['payload']['images'][0]['artifact_path']).read_bytes())
        self.assertEqual({'records':1,'candidates':0,'information':1,'groundings':2,'outbox':1},
                         self._counts(execution_id))

    def test_rejected_required_figure_is_not_reported_as_complete_coverage(self):
        execution_id=self._figure_repair_prepared()
        proposals=[self._figure_repair_proposal()]
        self.runtime.propose(execution_id,proposals,self._receipt('generator',{'proposals':proposals}))
        decisions=self._decisions('rejected')
        result=self.runtime.decide(execution_id,decisions,self._receipt('validator',{'decisions':decisions}))
        self.assertEqual('needs_human',result['state'])
        job=self.runtime.show(execution_id)
        self.assertEqual('rejected',job['records'][0]['disposition'])
        self.assertEqual({'records':1,'candidates':0,'information':0,'groundings':0,'outbox':0},
                         self._counts(execution_id))

    def test_same_job_and_concurrent_propose_decide_are_once_only(self):
        jobs = self._parallel(lambda runtime: runtime.start(self.data_id, self.profile))
        self.assertEqual(jobs[0]["execution_id"], jobs[1]["execution_id"])
        self.assertEqual([False, True], sorted(job["replayed"] for job in jobs))
        execution_id = jobs[0]["execution_id"]
        self.runtime.attach_parser(execution_id, self.directory, self.middle_path.name, 1)
        self.assertTrue(self.runtime.attach_parser(execution_id, self.directory, self.middle_path.name, 1)["replayed"])
        proposals = [self._proposal()]
        generator = self._receipt("generator", {"proposals": proposals})
        results = self._parallel(lambda runtime: runtime.propose(execution_id, proposals, generator))
        self.assertEqual([False, True], sorted(result["replayed"] for result in results))
        decisions = self._decisions("accepted")
        validator = self._receipt("validator", {"decisions": decisions})
        results = self._parallel(lambda runtime: runtime.decide(execution_id, decisions, validator))
        self.assertEqual([False, True], sorted(result["replayed"] for result in results))
        self.assertEqual({"records": 1, "candidates": 0, "information": 1, "groundings": 1, "outbox": 1},
                         self._counts(execution_id))
        self.assertEqual(4, len(self.runtime.show(execution_id)["events"]))

    def test_replay_checks_payload_before_returning_old_success(self):
        execution_id, proposals, generator = self._proposed()
        changed = deepcopy(proposals)
        changed[0]["content"] = "Different candidate content."
        self._assert_error("provider_receipt_mismatch", lambda: self.runtime.propose(execution_id, changed, generator))
        _, decisions, validator = self._accept(execution_id)
        changed = deepcopy(decisions)
        changed[0]["verdict"] = "rejected"
        self._assert_error("provider_receipt_mismatch", lambda: self.runtime.decide(execution_id, changed, validator))
        self.assertEqual(1, self._counts(execution_id)["information"])

    def test_frozen_profile_receipt_and_independent_validator(self):
        execution_id, proposals, generator = self._proposed()
        changed = deepcopy(generator)
        changed["profile"]["model"] = "different-model"
        self._assert_error("provider_profile_mismatch", lambda: self.runtime.propose(execution_id, proposals, changed))
        changed = deepcopy(generator)
        changed["thread_ref"] = "another-synthetic-generator"
        self._assert_error("proposal_retry_conflict", lambda: self.runtime.propose(execution_id, proposals, changed))
        with self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
            conn.execute("UPDATE compiler_runtime.operation_executions SET generator_receipt=%s WHERE execution_id=%s",
                         (Jsonb(changed), execution_id))
        decisions = self._decisions("accepted")
        validator = self._receipt("validator", {"decisions": decisions})
        validator["thread_ref"] = generator["thread_ref"]
        self._assert_error("validator_not_independent", lambda: self.runtime.decide(execution_id, decisions, validator))
        self.assertEqual(generator, self.runtime.show(execution_id)["generator_receipt"])
        self.assertEqual(0, self._counts(execution_id)["information"])

    def test_execution_failure_keeps_candidate_and_retry_keeps_job_identity(self):
        execution_id, proposals, generator = self._proposed()
        failed = self.runtime.mark_failed(execution_id, "synthetic_provider_failure")
        self.assertEqual("failed", failed["state"])
        self.assertIsNone(failed["records"][0]["disposition"])
        self.assertEqual(proposals, self.runtime.show(execution_id, include_input=True)["proposals"])
        retried = self.runtime.retry(execution_id)
        self.assertEqual((execution_id, "proposed", 2), (retried["execution_id"], retried["state"], retried["attempt"]))
        self.assertIsNone(retried["error_code"])
        self.assertEqual(generator, retried["generator_receipt"])
        self.assertEqual("completed", self._accept(execution_id)[0]["state"])

    def test_rejected_candidate_is_cleaned_but_needs_human_stays_unresolved(self):
        execution_id = self._prepared()
        proposals = [self._proposal(), self._proposal(image=True)]
        self.runtime.propose(execution_id, proposals, self._receipt("generator", {"proposals": proposals}))
        decisions = self._decisions("rejected", "needs_human")
        receipt = self._receipt("validator", {"decisions": decisions})
        self.assertEqual("needs_human", self.runtime.decide(execution_id, decisions, receipt)["state"])
        job = self.runtime.show(execution_id, include_input=True)
        self.assertEqual([proposals[1]], job["proposals"])
        self.assertEqual({"records": 2, "candidates": 1, "information": 0, "groundings": 0, "outbox": 0}, self._counts(execution_id))
        self.assertIsNotNone(self._row("SELECT resolved_at FROM compiler_runtime.records WHERE record_id=%s",
                                     (job["records"][0]["record_id"],))["resolved_at"])
        self.assertIsNone(self._row("SELECT resolved_at FROM compiler_runtime.records WHERE record_id=%s",
                                  (job["records"][1]["record_id"],))["resolved_at"])
        self.assertTrue(self.runtime.decide(execution_id, decisions, receipt)["replayed"])
        self.assertEqual("needs_human", self.runtime.retry(execution_id)["state"])

    def test_zero_output_is_explicit_and_creates_no_records_or_information(self):
        execution_id = self._prepared()
        receipt = self._receipt("generator", {"proposals": []})
        self.assertEqual("zero_output", self.runtime.propose(execution_id, [], receipt)["state"])
        self.assertTrue(self.runtime.propose(execution_id, [], receipt)["replayed"])
        self.assertEqual({"records": 0, "candidates": 0, "information": 0, "groundings": 0, "outbox": 0}, self._counts(execution_id))
        self.assertEqual("zero_output", self.runtime.start(self.data_id, self.profile)["state"])

    def test_unknown_grounding_and_incomplete_validation_leave_pending_work(self):
        execution_id = self._prepared()
        proposal = self._proposal()
        proposal["block_ids"] = ["/unknown/block"]
        receipt = self._receipt("generator", {"proposals": [proposal]})
        self._assert_error("invalid_candidate", lambda: self.runtime.propose(execution_id, [proposal], receipt))
        self.assertEqual("parsed", self.runtime.show(execution_id)["state"])
        self.assertEqual(0, self._counts(execution_id)["records"])
        proposals = [self._proposal()]
        self.runtime.propose(execution_id, proposals, self._receipt("generator", {"proposals": proposals}))
        receipt = self._receipt("validator", {"decisions": []})
        self._assert_error("invalid_validation", lambda: self.runtime.decide(execution_id, [], receipt))
        self.assertEqual(1, self._counts(execution_id)["candidates"])
        self.assertEqual("proposed", self.runtime.show(execution_id)["state"])

    def _insert_information(self, conn, record):
        return conn.execute("""INSERT INTO canonical_store.information
            (data_id,origin_record_id,kind,semantic_type,title,content,payload,identity_fingerprint,content_fingerprint)
            VALUES (%s,%s,'text','observation','Synthetic','Synthetic fixture',%s,%s,%s) RETURNING information_id""",
            (self.data_id, record["record_id"], Jsonb({"schema_version": "information-v1", "images": []}),
             record["identity_fingerprint"], record["content_fingerprint"])).fetchone()[0]

    def _insert_grounding(self, conn, information_id, parsed, block, *, data_id=None):
        conn.execute("""INSERT INTO canonical_store.information_groundings
            (information_id,data_id,parse_artifact_id,block_id,page_index,bbox,page_size,raw_locator,anchor_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (information_id, data_id or self.data_id, parsed["parse_artifact_id"], block["block_id"],
             block["page_index"], Jsonb(block["bbox"]), Jsonb(block["page_size"]), block["raw_locator"], block["anchor_sha256"]))

    def test_database_rejects_partial_acceptance_at_commit(self):
        execution_id, _, _ = self._proposed()
        job = self.runtime.show(execution_id, include_input=True)
        record, parsed = job["records"][0], job["parse"]
        for omitted in ("grounding", "accepted_record", "cleanup", "outbox"):
            with self.subTest(omitted=omitted), self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
                information_id = self._insert_information(conn, record)
                if omitted != "grounding":
                    self._insert_grounding(conn, information_id, parsed, parsed["bundle"]["blocks"][0])
                if omitted != "accepted_record":
                    conn.execute("""UPDATE compiler_runtime.records SET disposition='accepted',resolved_at=clock_timestamp(),
                        result_information_id=%s WHERE record_id=%s""", (information_id, record["record_id"]))
                if omitted != "cleanup":
                    conn.execute("DELETE FROM compiler_runtime.temporary_candidates WHERE record_id=%s", (record["record_id"],))
                if omitted != "outbox":
                    conn.execute("INSERT INTO compiler_runtime.outbox(record_id,information_id,operation) VALUES (%s,%s,'i2k')",
                                 (record["record_id"], information_id))
                conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertEqual({"records": 1, "candidates": 1, "information": 0, "groundings": 0, "outbox": 0}, self._counts(execution_id))

    def test_database_grounding_must_match_frozen_block_and_original_execution(self):
        execution_id, _, _ = self._proposed()
        job = self.runtime.show(execution_id, include_input=True)
        record, parsed = job["records"][0], job["parse"]
        original = parsed["bundle"]["blocks"][0]
        for key, changed in (("bbox", ["10", 20, 300, 60]), ("bbox", [11, 20, 300, 60]),
                             ("page_index", 1), ("anchor_sha256", "0" * 64), ("raw_locator", "/wrong"),
                             ("block_id", "/unknown"), ("page_size", [601, 800])):
            block = {**original, key: changed}
            with self.subTest(key=key, value=changed), self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
                information_id = self._insert_information(conn, record)
                self._insert_grounding(conn, information_id, parsed, block)
        other_job = self._prepared(generation=2)
        other_parse = self.runtime.show(other_job, include_input=True)["parse"]
        with self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
            information_id = self._insert_information(conn, record)
            self._insert_grounding(conn, information_id, other_parse, other_parse["bundle"]["blocks"][0])
        self.assertEqual(0, self._counts(execution_id)["information"])

    def test_cross_data_references_are_rejected(self):
        execution_id, _, _ = self._proposed()
        other_data = self._import_fixture("other.pdf")
        record = self.runtime.show(execution_id)["records"][0]
        with self.assertRaises(psycopg.errors.ForeignKeyViolation), psycopg.connect(self.dsn) as conn:
            conn.execute("""INSERT INTO compiler_runtime.records
                (subtype,execution_id,data_id,ordinal,identity_fingerprint,content_fingerprint,context_fingerprint)
                VALUES ('D2IRecord',%s,%s,7,%s,%s,%s)""", (execution_id, other_data, "a" * 64, "b" * 64, "c" * 64))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation), psycopg.connect(self.dsn) as conn:
            conn.execute("""INSERT INTO canonical_store.information
                (data_id,origin_record_id,kind,semantic_type,title,content,payload,identity_fingerprint,content_fingerprint)
                VALUES (%s,%s,'text','observation','Synthetic','Synthetic',%s,%s,%s)""",
                (other_data, record["record_id"], Jsonb({"schema_version":"information-v1"}), "a" * 64, "b" * 64))
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertEqual(0, self._counts(execution_id)["information"])

    def test_information_terminal_record_and_grounding_set_are_immutable(self):
        execution_id, proposals, _ = self._proposed()
        result, _, _ = self._accept(execution_id)
        information_id = result["information_ids"][0]
        job = self.runtime.show(execution_id, include_input=True)
        record = job["records"][0]
        statements = [
            ("UPDATE canonical_store.information SET content='changed' WHERE information_id=%s", (information_id,)),
            ("UPDATE compiler_runtime.records SET disposition='rejected',result_information_id=NULL WHERE record_id=%s", (record["record_id"],)),
            ("UPDATE compiler_runtime.operation_executions SET state='proposed' WHERE execution_id=%s", (execution_id,)),
            ("INSERT INTO compiler_runtime.temporary_candidates(record_id,body) VALUES (%s,%s)", (record["record_id"], Jsonb(proposals[0]))),
        ]
        for sql, params in statements:
            with self.subTest(sql=sql), self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
                conn.execute(sql, params)
        with self.assertRaises(psycopg.Error), psycopg.connect(self.dsn) as conn:
            self._insert_grounding(conn, information_id, job["parse"], job["parse"]["bundle"]["blocks"][1])
        self.assertEqual(proposals[0]["content"], self.runtime.information(information_id=information_id)["information"][0]["content"])
        self.assertEqual({"records": 1, "candidates": 0, "information": 1, "groundings": 1, "outbox": 1}, self._counts(execution_id))

    def test_parser_bytes_changed_during_publication_are_not_registered(self):
        execution_id = self.runtime.start(self.data_id, self.profile)["execution_id"]
        original_publish = self.runtime._publish

        def mutate_before_publish(path):
            if Path(path) == self.middle_path:
                changed = json.loads(path.read_text(encoding="utf-8"))
                changed["synthetic_mutation"] = True
                path.write_text(json.dumps(changed), encoding="utf-8")
            return original_publish(path)

        with patch.object(self.runtime, "_publish", side_effect=mutate_before_publish):
            self._assert_error("parser_artifact_changed", lambda: self.runtime.attach_parser(
                execution_id, self.directory, self.middle_path.name, 1))
        job = self.runtime.show(execution_id, include_input=True)
        self.assertEqual("prepared", job["state"])
        self.assertIsNone(job["parse"])

    def test_parser_export_recovers_durable_files_and_never_overwrites_conflicting_bytes(self):
        execution_id = self._prepared()
        manifest = self.runtime.show(execution_id, include_input=True)["parse"]["manifest"]
        expected_middle = self.middle_path.read_bytes()
        (self.directory / "images/figure.png").unlink()
        self.middle_path.unlink()
        target = self.base / "recovered-parser-output"
        first = self.runtime.export_parser(execution_id, target)
        self.assertEqual(len(manifest["files"]), first["file_count"])
        self.assertEqual(self.middle_path.name, first["middle"])
        self.assertEqual(expected_middle, (target / first["middle"]).read_bytes())
        self.assertEqual(self.image_bytes, (target / "images/figure.png").read_bytes())
        for name, reference in manifest["files"].items():
            restored = (target / name).read_bytes()
            self.assertEqual(reference["sha256"], sha256(restored).hexdigest())
            self.assertEqual(reference["byte_size"], len(restored))
        self.assertEqual(first, self.runtime.export_parser(execution_id, target))
        conflicting = b"Existing destination bytes must be preserved."
        (target / "images/figure.png").write_bytes(conflicting)
        self._assert_error("export_conflict", lambda: self.runtime.export_parser(execution_id, target))
        self.assertEqual(conflicting, (target / "images/figure.png").read_bytes())
        self.assertEqual("parsed", self.runtime.show(execution_id)["state"])

    def test_installed_migration_checksums_match_checkout_without_rewriting_history(self):
        with psycopg.connect(self.dsn) as conn:
            installed = conn.execute("SELECT version,checksum FROM compiler_runtime.schema_migrations ORDER BY version").fetchall()
        self.assertEqual([(version, migration_source(version)[1]) for version in MIGRATIONS], installed)

    def test_every_t03_opaque_id_rejects_non_rfc_variant_even_with_version_seven_bits(self):
        execution_id, _, _ = self._proposed()
        job = self.runtime.show(execution_id, include_input=True)
        # The version nibble is 7, but the variant is not RFC 9562. PostgreSQL
        # returns NULL here; a bare CHECK(uuid_extract_version(id)=7) accepts it.
        non_rfc_id = "00000000-0000-7000-0000-000000000001"
        with psycopg.connect(self.dsn) as conn:
            try:
                self.assertIsNone(conn.execute("SELECT uuid_extract_version(%s::uuid)", (non_rfc_id,)).fetchone()[0])
                information_id = self._insert_information(conn, job["records"][0])
                self._insert_grounding(conn, information_id, job["parse"], job["parse"]["bundle"]["blocks"][0])
                grounding_id = conn.execute("SELECT grounding_id FROM canonical_store.information_groundings WHERE information_id=%s",
                                            (information_id,)).fetchone()[0]
                outbox_id = conn.execute("""INSERT INTO compiler_runtime.outbox(record_id,information_id,operation)
                    VALUES (%s,%s,'i2k') RETURNING event_id""", (job["records"][0]["record_id"], information_id)).fetchone()[0]
                event_id = conn.execute("SELECT event_id FROM compiler_runtime.execution_events WHERE execution_id=%s LIMIT 1",
                                        (execution_id,)).fetchone()[0]
                rows = [
                    ("compiler_runtime", "profiles", "profile_id", job["profile_id"]),
                    ("compiler_runtime", "operation_executions", "execution_id", execution_id),
                    ("compiler_runtime", "parse_artifacts", "parse_artifact_id", job["parse"]["parse_artifact_id"]),
                    ("compiler_runtime", "execution_events", "event_id", event_id),
                    ("compiler_runtime", "records", "record_id", job["records"][0]["record_id"]),
                    ("canonical_store", "information", "information_id", information_id),
                    ("canonical_store", "information_groundings", "grounding_id", grounding_id),
                    ("compiler_runtime", "outbox", "event_id", outbox_id),
                ]
                for schema, table, id_column, original_id in rows:
                    # Clone valid rows so no unrelated missing FK or field can
                    # masquerade as UUID rejection. Each attempt is a savepoint.
                    query = sql.SQL("""INSERT INTO {relation}
                        SELECT (jsonb_populate_record(NULL::{relation},
                            to_jsonb(source) || jsonb_build_object(%s::text,%s::text))).*
                        FROM {relation} source WHERE {id_column}=%s""").format(
                            relation=sql.Identifier(schema, table), id_column=sql.Identifier(id_column))
                    with self.subTest(table=table), self.assertRaises(psycopg.errors.CheckViolation) as caught:
                        with conn.transaction():
                            conn.execute(query, (id_column, non_rfc_id, original_id))
                    self.assertEqual(f"{table}_{id_column}_check", caught.exception.diag.constraint_name)
            finally:
                # These rows only support the constraint probes. No incomplete
                # Information or pending outbox is committed by this test.
                conn.rollback()
        self.assertEqual({"records": 1, "candidates": 1, "information": 0, "groundings": 0, "outbox": 0},
                         self._counts(execution_id))


if __name__ == "__main__":
    unittest.main()
