"""Focused PG check for resumable batched I2K; no model calls."""

from hashlib import sha256
from copy import deepcopy
import os
import unittest

from palimpsest import batched_i2k, cli, multi_source_i2k
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import MODEL
from palimpsest.errors import PalimpsestError
from palimpsest.codex_provider import PROFILE as CODEX_MODEL

import test_selection_runtime as selection_fixture


class BatchedI2KBoundaryTests(unittest.TestCase):
    def test_batch_catalog_limits_existing_k_and_edges(self):
        snapshot = {"comparison_catalog": {"schema_version": "bge-m3-batch-comparison-catalog-v1",
            "batches": [{"batch_id": "b0001", "revision_ids": ["r2"]}]},
            "existing_nodes": [{"knode_id": "k1", "knode_revision_id": "r1"},
                               {"knode_id": "k2", "knode_revision_id": "r2"}],
            "existing_edges": [{"from_knode_id": "k1", "to_knode_id": "k2"},
                               {"from_knode_id": "k2", "to_knode_id": "k2"}]}
        nodes, edges = batched_i2k._existing(snapshot, {"batch_id": "b0001"})
        self.assertEqual([node["knode_revision_id"] for node in nodes], ["r2"])
        self.assertEqual(edges, [{"from_knode_id": "k2", "to_knode_id": "k2"}])

    def test_previous_review_is_scoped_to_the_delivered_batch(self):
        snapshot = {"selection_feedback": {"generator_reviews": [
                {"information_id": "i1"}, {"information_id": "i2"}],
            "validator_reviews": [{"information_id": "i1"}, {"information_id": "i2"}],
            "source_requests": [{"payload": {"information_ids": ["i1"]}},
                                {"payload": {"information_ids": ["i2"]}}],
            "source_review": {"manifest": {"schema_version": "source-review-v1", "targets": [
                    {"target_id": "t1"}, {"target_id": "t2"}]},
                "generator_reviews": [
                    {"target_id": "t1", "items": [{"item_key": "x1"}]},
                    {"target_id": "t2", "items": [{"item_key": "x2"}]}],
                "validation": {"targets": [{"target_id": "t1"}, {"target_id": "t2"}],
                    "items": [{"item_key": "x1"}, {"item_key": "x2"}],
                    "bindings": [{"item_key": "x1"}, {"item_key": "x2"}],
                    "pending_target_ids": ["t1", "t2"], "pending_item_keys": ["x1", "x2"]}}}}
        value = batched_i2k._feedback(snapshot,
            {"batch_id": "b0001", "information_ids": ["i1"], "target_ids": ["t1"]})
        self.assertEqual(value["generator_reviews"], [{"information_id": "i1"}])
        self.assertEqual(value["source_review"]["validation"]["pending_item_keys"], ["x1"])
        self.assertEqual(value["source_review"]["manifest"]["targets"], [{"target_id": "t1"}])

    def test_validator_catalog_is_compact_and_semantically_complete(self):
        summary = batched_i2k._candidate_summary({"candidate_key": "c", "statement": "s",
            "semantic_payload": {"large": "payload"}, "identity_fingerprint": "i",
            "content_fingerprint": "v"})
        self.assertNotIn("semantic_payload", summary)
        self.assertNotIn("identity_fingerprint", summary)
        self.assertEqual((summary["candidate_key"], summary["statement"]), ("c", "s"))

    def test_validator_reuses_delivered_block_text_by_hash(self):
        candidate = {"candidate_key": "c", "evidence": [
            {"source_block_id": "block", "quote": "long source paragraph"},
            {"information_id": "i", "quote": "unique short quote"}]}
        projected = batched_i2k._validation_candidate(candidate)
        self.assertEqual(projected["evidence"][0]["quote_sha256"],
                         sha256(b"long source paragraph").hexdigest())
        self.assertNotIn("quote", projected["evidence"][0])
        self.assertEqual(projected["evidence"][1]["quote"], "unique short quote")
        self.assertIn("quote", candidate["evidence"][0])

    def test_mutual_reuse_chooses_one_stable_root(self):
        decisions = [{"candidate_key": key, "verdict": "reused",
            "equivalent_candidate_key": target, "equivalent_revision_id": None,
            "reason_codes": ["equivalent"], "reason": "Same meaning."}
            for key, target in (("b", "c"), ("c", "a"), ("a", "b"))]
        rows = {row["candidate_key"]: row
                for row in batched_i2k._canonicalize_reuse_cycles(decisions)}
        self.assertEqual(rows["a"]["verdict"], "accepted")
        self.assertIsNone(rows["a"]["equivalent_candidate_key"])
        self.assertEqual(rows["b"]["equivalent_candidate_key"], "c")
        self.assertEqual(rows["c"]["equivalent_candidate_key"], "a")
        self.assertEqual(decisions[2]["verdict"], "reused")

    def test_fully_delivered_block_enum_is_deterministic(self):
        batch = {"target_slices": [
            {"target_id": "t2", "source_block_id": "z", "char_ranges": [[0, 1]],
             "full_char_ranges": [[0, 1]]},
            {"target_id": "t1", "source_block_id": "a", "char_ranges": [[0, 1]],
             "full_char_ranges": [[0, 1]]},
        ]}
        self.assertEqual(batched_i2k._fully_delivered_blocks(batch), ["a", "z"])

    def test_generation_schema_omits_impossible_block_evidence_branch(self):
        schema = {"properties": {"nodes": {"items": {"properties": {"evidence": {
            "items": {"anyOf": [
                {"properties": {"information_id": {"enum": []},
                                "source_block_id": {"enum": []}}},
                {"properties": {"information_id": {"enum": []},
                                "quote": {"type": "string"},
                                "media_sha256": {"enum": []}}},
            ]}}}}}, "reviews": {"items": {"properties": {
                "information_id": {"enum": []}}}}, "source_requests": {"items": {
                    "properties": {"information_ids": {"items": {"enum": []}},
                                   "data_id": {"enum": []}}}}}}
        batch = {"information_ids": ["i"], "image_sha256s": ["m"], "target_slices": [
            {"target_id": "t", "information_id": "i", "source_block_id": None,
             "char_ranges": [], "full_char_ranges": [], "media_sha256s": ["m"],
             "data_id": "d"}]}
        restricted = batched_i2k._restrict_generation_schema(schema, batch)
        branches = restricted["properties"]["nodes"]["items"]["properties"][
            "evidence"]["items"]["anyOf"]
        self.assertEqual(len(branches), 1)
        self.assertNotIn("source_block_id", branches[0]["properties"])
        self.assertEqual(branches[0]["properties"]["media_sha256"]["enum"], ["m"])
        self.assertEqual(branches[0]["properties"]["quote"]["enum"], [""])

    def test_only_legacy_source_block_enum_order_is_compatible(self):
        schema = {"properties": {"nodes": {"items": {"properties": {"evidence": {
            "items": {"anyOf": []}}}}}}}
        schema["properties"]["nodes"]["items"]["properties"]["evidence"]["items"][
            "anyOf"].append({"properties": {"source_block_id": {"enum": ["a", "z"]}}})
        legacy = deepcopy(schema)
        legacy["properties"]["nodes"]["items"]["properties"]["evidence"]["items"][
            "anyOf"][0]["properties"]["source_block_id"]["enum"].reverse()
        self.assertTrue(batched_i2k._legacy_schema_hash_matches(schema, digest(legacy)))
        legacy["unexpected"] = True
        self.assertFalse(batched_i2k._legacy_schema_hash_matches(schema, digest(legacy)))

    def test_cli_can_freeze_the_terra_fallback_provider(self):
        args = cli._parser().parse_args(["knowledge", "prepare", "--operation", "i2k",
            "--data-id", "a" * 64, "--request-id", "01a0a425-9e86-79b1-9446-995ab688c8c9",
            "--input", "source.json", "--provider", "codex-terra"])
        self.assertEqual(args.provider, "codex-terra")

    def test_partial_batch_cannot_claim_the_whole_block_or_an_undelivered_anchor(self):
        batch = {"batch_id": "b0001", "information_ids": ["i"], "target_ids": ["t"],
            "image_sha256s": [], "target_slices": [{"target_id": "t", "information_id": "i",
                "source_block_id": "block", "char_ranges": [[0, 5]], "full_char_ranges": [[0, 10]],
                "media_sha256s": [], "text": [{"content": "abcde"}]}]}
        response = {"nodes": [{"candidate_key": "c", "evidence": [
                {"information_id": "i", "source_block_id": "block"}]}],
            "reviews": [{"information_id": "i"}], "source_requests": [], "complete": True,
            "coverage_notes": [], "source_reviews": [{"target_id": "t", "items": [{
                "candidate_keys": ["c"], "anchors": [
                    {"char_start": 6, "char_end": 7, "media_sha256": None}]}]}]}
        with self.assertRaises(PalimpsestError):
            batched_i2k._validate_generator_response(batch, response)

    def test_placeholder_anchor_uses_the_exact_candidate_modality(self):
        batch = {"batch_id": "b0001", "information_ids": ["i"], "target_ids": ["t"],
            "image_sha256s": ["m"], "target_slices": [{"target_id": "t", "information_id": "i",
                "data_id": "d", "source_block_id": "block", "char_ranges": [[2, 5]],
                "full_char_ranges": [[2, 5]],
                "media_sha256s": ["m"], "text": [{"content": "abc"}]}]}
        response = {"nodes": [{"candidate_key": "c", "evidence": [
                {"information_id": "i", "source_block_id": "block"}]}],
            "reviews": [{"information_id": "i"}], "source_requests": [], "complete": True,
            "coverage_notes": [], "source_reviews": [{"target_id": "t", "items": [{
                "candidate_keys": ["c"], "anchors": [
                    {"char_start": None, "char_end": None, "media_sha256": None}]}]}]}
        normalized = batched_i2k._normalize_generator_anchors(batch, response)
        self.assertEqual(normalized["source_reviews"][0]["items"][0]["anchors"], [
            {"char_start": 2, "char_end": 5, "media_sha256": None}])
        batched_i2k._validate_generator_response(batch, normalized)
        response["source_reviews"][0]["items"][0]["anchors"] = []
        self.assertEqual(batched_i2k._normalize_generator_anchors(batch, response)[
            "source_reviews"][0]["items"][0]["anchors"], [
                {"char_start": 2, "char_end": 5, "media_sha256": None}])
        response["source_reviews"][0]["items"][0]["candidate_keys"] = []
        normalized = batched_i2k._normalize_generator_anchors(batch, response)
        self.assertIn("c", {key for item in normalized["source_reviews"][0]["items"]
                            for key in item["candidate_keys"]})

    def test_namespace_applies_deterministic_anchor_normalization(self):
        batch = {"batch_id": "b0001", "information_ids": ["i"], "target_ids": ["t"],
            "image_sha256s": [], "target_slices": [{"target_id": "t", "information_id": "i",
                "data_id": "d", "source_block_id": "block", "char_ranges": [[2, 5]],
                "full_char_ranges": [[2, 5]], "media_sha256s": [], "text": [{"content": "abc"}]}]}
        response = {"nodes": [{"candidate_key": "raw", "evidence": [
                {"information_id": "i", "source_block_id": "block"}]}],
            "reviews": [{"information_id": "i", "candidate_keys": ["raw"]}],
            "source_requests": [], "complete": True, "coverage_notes": [],
            "source_reviews": [{"target_id": "t", "items": [{"item_key": "raw-item",
                "candidate_keys": ["raw"], "anchors": [], "label": "x",
                "disposition": "selected", "reason": "x"}]}]}
        value = batched_i2k._namespace_generator(batch, response)
        self.assertEqual(value["source_reviews"][0]["items"][0]["anchors"], [
            {"char_start": 2, "char_end": 5, "media_sha256": None}])
        self.assertEqual(value["nodes"][0]["candidate_key"], "b0001.c0001")

    def test_binding_moves_a_candidate_out_of_an_unrelated_target(self):
        batch = {"batch_id": "b0001", "information_ids": ["i"], "target_ids": ["t1", "t2"],
            "image_sha256s": ["m"], "target_slices": [
                {"target_id": "t1", "information_id": "i", "data_id": "d",
                 "source_block_id": "block1", "char_ranges": [[0, 3]], "full_char_ranges": [[0, 3]],
                 "media_sha256s": [], "text": [{"content": "abc"}]},
                {"target_id": "t2", "information_id": "i", "data_id": "d",
                 "source_block_id": "block2", "char_ranges": [], "full_char_ranges": [],
                 "media_sha256s": ["m"], "text": []}]}
        response = {"nodes": [{"candidate_key": "c", "statement": "x", "evidence": [
                {"information_id": "i", "source_block_id": "block1"}]}],
            "source_reviews": [
                {"target_id": "t1", "items": [{"item_key": "a", "candidate_keys": [],
                    "anchors": [{"char_start": 0, "char_end": 3, "media_sha256": None}],
                    "label": "a", "disposition": "context_only", "reason": "a"}]},
                {"target_id": "t2", "items": [{"item_key": "b", "candidate_keys": ["c"],
                    "anchors": [{"char_start": None, "char_end": None, "media_sha256": "m"}],
                    "label": "b", "disposition": "selected", "reason": "b"}]}]}
        value = batched_i2k._normalize_generator_anchors(batch, response)
        unrelated = value["source_reviews"][1]["items"][0]
        self.assertEqual((unrelated["candidate_keys"], unrelated["disposition"]), ([], "needs_review"))
        self.assertIn("c", {key for item in value["source_reviews"][0]["items"]
                            for key in item["candidate_keys"]})

    def test_validator_repeated_coverage_rows_are_held(self):
        batch = {"information_ids": ["info-a", "info-b"], "target_ids": ["target-a"]}
        response = {"decisions": [], "reviews": [
            {"information_id": "info-a", "verdict": "confirmed", "reason_codes": ["ok"],
             "reason": "Reviewed."},
            {"information_id": "info-a", "verdict": "needs_review", "reason_codes": ["gap"],
             "reason": "Repeated instead of covering info-b."}],
            "complete": True, "source_review_decisions": {"targets": [
                {"target_id": "target-a", "verdict": "confirmed", "reason": "Reviewed."}],
                "items": [
                    {"item_key": "item-a", "verdict": "confirmed", "reason": "Reviewed."},
                    {"item_key": "item-a", "verdict": "confirmed", "reason": "Repeated."}]}}
        value = batched_i2k._normalize_validator_coverage(
            batch, response, [], ["item-a", "item-b"])
        self.assertFalse(value["complete"])
        self.assertEqual([row["information_id"] for row in value["reviews"]], ["info-a", "info-b"])
        self.assertEqual(value["reviews"][0]["verdict"], "needs_review")
        self.assertEqual(value["reviews"][1]["reason_codes"], ["validator_coverage_missing"])
        self.assertEqual(value["source_review_decisions"]["items"][1]["verdict"], "needs_review")


@unittest.skipUnless(os.environ.get("PALIMPSEST_TEST_DSN"), "Requires isolated PostgreSQL")
class BatchedI2KRuntimeTests(unittest.TestCase):
    def setUp(self):
        case = selection_fixture.SelectionRuntimeTests("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        self.helper = case.helper
        self.runtime = self.helper.runtime
        self.packet = multi_source_i2k.combine_packets([self.helper.packet])
        self.job = self.runtime.prepare("i2k", self.helper.data_id, self.helper.repo.allocate_id(),
                                        self.packet, selection=True, source_review=True)
        self.media = {item["sha256"]: item["byte_size"] for item in self.packet["media_assets"]}

    def _receipt(self, batch, response, phase):
        request = batch["request"]
        return {"profile": MODEL, "input_sha256": request["input_sha256"],
            "output_sha256": digest(response), "provider_ref": f"synthetic-{phase}-{batch['batch_id']}",
            "actual_delivery": True, "usage": {},
            "prompt_sha256": sha256(request["prompt"].encode()).hexdigest(),
            "schema_sha256": digest(request["schema"]),
            "image_attachments": [{"sha256": key, "byte_size": self.media[key]}
                                  for key in request["image_sha256s"]],
            "original_pdf_delivered": False,
            "delivered_information_ids": request["delivered_information_ids"],
            "delivered_source_target_ids": request["delivered_source_target_ids"],
            "batch_id": request["batch_id"]}

    @staticmethod
    def _anchor(batch, target_id):
        rows = [row for row in batch["target_slices"] if row["target_id"] == target_id]
        span = next((span for row in rows for span in row["char_ranges"]), None)
        image = next((image for row in rows for image in row["media_sha256s"]), None)
        return ({"char_start": span[0], "char_end": span[1], "media_sha256": None} if span else
                {"char_start": None, "char_end": None, "media_sha256": image} if image else None)

    def test_runtime_freezes_only_current_batch_catalog_revisions(self):
        accepted = self.helper.accept(self.helper.prepare())
        revision = accepted["records"][0]["result_node_revision_id"]
        plan = batched_i2k.requests({"input_snapshot": self.job["input_snapshot"],
                                     "input_digest": self.job["input_digest"]}, "generator")
        catalog = {"schema_version": "bge-m3-batch-comparison-catalog-v1",
            "batches": [{"batch_id": batch["batch_id"], "revision_ids": [revision]}
                        for batch in plan["batches"]],
            "embedding_profile_sha256": "a" * 64, "embedding_result_sha256": "b" * 64}
        job = self.runtime.prepare("i2k", self.helper.data_id, self.helper.repo.allocate_id(),
            self.packet, selection=True, source_review=True, comparison_catalog=catalog)
        self.assertEqual(job["input_snapshot"]["comparison_catalog"], catalog)
        filtered = batched_i2k.requests({"input_snapshot": job["input_snapshot"],
                                         "input_digest": job["input_digest"]}, "generator")
        self.assertTrue(all(revision in batch["request"]["prompt"] for batch in filtered["batches"]))
        catalog["batches"][0]["revision_ids"] = [self.helper.repo.allocate_id()]
        with self.assertRaises(PalimpsestError) as caught:
            self.runtime.prepare("i2k", self.helper.data_id, self.helper.repo.allocate_id(),
                self.packet, selection=True, source_review=True, comparison_catalog=catalog)
        self.assertEqual(caught.exception.code, "invalid_i2k_comparison_catalog")

    def test_batches_are_exhaustive_and_commit_only_after_independent_merge(self):
        terra = self.runtime.prepare("i2k", self.helper.data_id, self.helper.repo.allocate_id(),
                                     self.packet, selection=True, source_review=True,
                                     model_profile=CODEX_MODEL)
        self.assertEqual(terra["profile"]["model"], CODEX_MODEL)
        generator_context = {"input_snapshot": self.job["input_snapshot"],
                             "input_digest": self.job["input_digest"]}
        plan = batched_i2k.requests(generator_context, "generator")
        evidence_batch = next(batch for batch in plan["batches"]
                              if any(row["source_block_id"] and row["char_ranges"]
                                     for row in batch["target_slices"]))
        evidence_target = next(row for row in evidence_batch["target_slices"]
                               if row["source_block_id"] and row["char_ranges"])
        exchanges = []
        for batch in plan["batches"]:
            candidate = []
            raw_key = "claim" if batch["batch_id"] == evidence_batch["batch_id"] else None
            if raw_key:
                candidate = [{"candidate_key": raw_key, "kind": "observation",
                    "statement": "The synthetic source records a test observation.",
                    "semantic_payload": {"subject": "synthetic source", "relation": "records",
                        "object": "a test observation", "polarity": "positive", "quantifier": "one",
                        "scope": "fixture", "conditions": [], "time_range": ""},
                    "evidence": [{"information_id": evidence_target["information_id"],
                        "source_block_id": evidence_target["source_block_id"], "source_role": "results"}],
                    "uncertainties": [], "identity_scope": "source",
                    "selection_reason": "Useful explicit fixture observation.",
                    "source_data_id": evidence_target["data_id"],
                    "claim_basis": "explicit_source_content", "is_inferred": False}]
            reviews = []
            for identifier in batch["information_ids"]:
                keys = [raw_key] if raw_key and identifier == evidence_target["information_id"] else []
                reviews.append({"information_id": identifier,
                    "disposition": "selected" if keys else "context_only",
                    "candidate_keys": keys, "reason": "Synthetic exhaustive batch review."})
            source_rows = []
            for target_id in batch["target_ids"]:
                anchor = self._anchor(batch, target_id)
                selected = raw_key and target_id == evidence_target["target_id"]
                source_rows.append({"target_id": target_id, "items": [{"item_key": "item-" + target_id[:8],
                    "label": "Synthetic reviewed source item",
                    "disposition": "selected" if selected else "context_only",
                    "candidate_keys": [raw_key] if selected else [],
                    "anchors": [anchor] if anchor else [], "reason": "Synthetic source review."}]})
            response = {"nodes": candidate, "reviews": reviews, "source_requests": [],
                        "complete": True, "coverage_notes": [], "source_reviews": source_rows}
            exchanges.append({"response": response,
                              "receipt": self._receipt(batch, response, "generator")})
        generated = batched_i2k.aggregate(generator_context, "generator", exchanges, MODEL)
        staged = self.runtime.stage(self.job["execution_id"], generated["response"], generated["receipt"])
        self.assertEqual(len(staged["candidates"]), 1)

        validation_context = {**staged, "validation_context_sha": staged["validation_context_sha"]}
        plan = batched_i2k.requests(validation_context, "validator")
        generator_reviews = {row["target_id"]: row for row in validation_context["source_reviews"]}
        candidate_key = staged["candidates"][0]["candidate_key"]
        exchanges = []
        for batch in plan["batches"]:
            assigned = [candidate_key] if candidate_key.startswith(batch["batch_id"] + ".") else []
            decisions = [{"candidate_key": candidate_key, "verdict": "accepted",
                "equivalent_candidate_key": None, "equivalent_revision_id": None,
                "reason_codes": ["synthetic_fixture"], "reason": "Synthetic independent validation.",
                "scope_correct": True, "importance_justified": True, "source_explicit": True,
                "no_novel_inference": True, "source_identity_preserved": True}] if assigned else []
            items = [item["item_key"] for target in batch["target_ids"]
                     for item in generator_reviews[target]["items"]
                     if item["item_key"].startswith(batch["batch_id"] + ".")]
            response = {"decisions": decisions,
                "reviews": [{"information_id": identifier, "verdict": "confirmed",
                             "reason_codes": ["synthetic_fixture"],
                             "reason": "Synthetic independent coverage."}
                            for identifier in batch["information_ids"]],
                "complete": True, "source_review_decisions": {
                    "targets": [{"target_id": target, "verdict": "confirmed",
                                 "reason": "Synthetic independent target review."}
                                for target in batch["target_ids"]],
                    "items": [{"item_key": item, "verdict": "confirmed",
                               "reason": "Synthetic independent item review."} for item in items]}}
            exchanges.append({"response": response,
                              "receipt": self._receipt(batch, response, "validator")})
        validated = batched_i2k.aggregate(validation_context, "validator", exchanges, MODEL)
        result = self.runtime.decide(self.job["execution_id"], validated["response"], validated["receipt"])
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(result["records"]), 1)

if __name__ == "__main__":
    unittest.main()
