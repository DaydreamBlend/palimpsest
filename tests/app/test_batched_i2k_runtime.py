"""Focused PG check for resumable batched I2K; no model calls."""

from hashlib import sha256
import os
import unittest

from palimpsest import batched_i2k, multi_source_i2k
from palimpsest.i2k import digest
from palimpsest.knowledge_runtime import MODEL
from palimpsest.errors import PalimpsestError

import test_selection_runtime as selection_fixture


class BatchedI2KBoundaryTests(unittest.TestCase):
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

    def test_batches_are_exhaustive_and_commit_only_after_independent_merge(self):
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
