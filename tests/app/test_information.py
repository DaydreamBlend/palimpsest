"""Pure-domain T03 checks; no parser/model/DB execution or semantic acceptance."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.information import (
    GENERATOR_SCHEMA, PROPOSAL_SCHEMA, VALIDATOR_SCHEMA,
    fingerprints, validate_decisions, validate_proposal,
)


class InformationTests(unittest.TestCase):
    def setUp(self):
        self.data_id = sha256(b"original PDF bytes").hexdigest()
        self.blocks = {
            "p0-b1": {
                "block_id": "p0-b1", "type": "text", "page_index": 0,
                "bbox": [10, 20, 200, 80], "page_size": [612, 792],
                "text": "The sample contains 42 observations.", "image_paths": [],
                "raw_locator": "/0", "anchor_sha256": sha256(b"source text anchor").hexdigest(),
            },
            "p0-b2": {
                "block_id": "p0-b2", "type": "image", "page_index": 0,
                "bbox": [20, 100, 300, 350], "page_size": [612, 792],
                "text": "Figure 1: observations by category.",
                "image_paths": [{"path": "images/figure-1.png", "sha256": sha256(b"image bytes").hexdigest()}],
                "raw_locator": "/1", "anchor_sha256": sha256(b"source figure anchor").hexdigest(),
            },
        }
        self.proposal = {
            "kind": "text", "semantic_type": "observation", "title": "Sample size",
            "content": "The sample in this paper contains 42 observations.",
            "block_ids": ["p0-b1"], "image_block_id": None,
        }

    def assert_invalid(self, action, code="invalid_candidate"):
        with self.assertRaises(PalimpsestError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(caught.exception.exit_code, 4)

    def image_proposal(self):
        return {**self.proposal, "kind": "image", "semantic_type": "figure",
                "block_ids": ["p0-b1", "p0-b2"], "image_block_id": "p0-b2"}

    def decision(self, ordinal=0, verdict="accepted"):
        return {"ordinal": ordinal, "verdict": verdict,
                "reason_codes": ["source_fidelity"], "reason": "The statement matches the cited source."}

    def test_output_schemas_are_strict_json_objects_with_all_fields_required(self):
        for schema in (GENERATOR_SCHEMA, VALIDATOR_SCHEMA, PROPOSAL_SCHEMA,
                       VALIDATOR_SCHEMA["properties"]["decisions"]["items"]):
            with self.subTest(schema=schema):
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(set(schema["required"]), set(schema["properties"]))
        self.assertEqual(json.loads(json.dumps(GENERATOR_SCHEMA)), GENERATOR_SCHEMA)
        self.assertEqual(PROPOSAL_SCHEMA["properties"]["kind"]["enum"], ["text", "image"])

    def test_normalization_is_unicode_safe_and_preserves_internal_structure(self):
        proposal = {**self.proposal, "title": "  Cafe\u0301  ",
                    "content": "  First line.\r\nSecond  line.\rThird line.  "}
        before = deepcopy(proposal)
        normalized = validate_proposal(proposal, self.blocks)
        self.assertEqual(normalized["title"], "Café")
        self.assertEqual(normalized["content"], "First line.\nSecond  line.\nThird line.")
        self.assertEqual(proposal, before)

    def test_missing_extra_and_wrong_typed_proposal_fields_are_rejected(self):
        cases = [{**self.proposal, "approved": True}, {k: v for k, v in self.proposal.items() if k != "image_block_id"}]
        for field, value in (("kind", "table"), ("semantic_type", "decision"),
                             ("title", "  "), ("content", None), ("content", "NUL\x00text"),
                             ("content", "\ud800"), ("block_ids", "p0-b1"), ("block_ids", [])):
            cases.append({**self.proposal, field: value})
        for proposal in cases:
            with self.subTest(proposal=repr(proposal)):
                self.assert_invalid(lambda: validate_proposal(proposal, self.blocks))

    def test_groundings_require_known_unique_consistent_block_references(self):
        for block_ids in (["unknown"], ["p0-b1", "p0-b1"], [None], [[]]):
            with self.subTest(block_ids=block_ids):
                self.assert_invalid(lambda: validate_proposal({**self.proposal, "block_ids": block_ids}, self.blocks))
        blocks = deepcopy(self.blocks)
        blocks["p0-b1"]["block_id"] = "different"
        self.assert_invalid(lambda: validate_proposal(self.proposal, blocks))

    def test_invalid_page_bbox_and_anchor_are_not_valid_groundings(self):
        for field, value in (("page_index", True), ("page_index", -1),
                             ("bbox", [0, 0, float("nan"), 20]), ("bbox", [0, 0, float("inf"), 20]),
                             ("bbox", [0, 0, True, 20]), ("bbox", [0, 0, 0, 20]),
                             ("bbox", [-1, 0, 10, 20]), ("bbox", [0, 0, 700, 20]),
                             ("bbox", [0, 0, 20]), ("page_size", [0, 0]),
                             ("anchor_sha256", "invalid")):
            blocks = deepcopy(self.blocks)
            blocks["p0-b1"][field] = value
            with self.subTest(field=field, value=value):
                self.assert_invalid(lambda: validate_proposal(self.proposal, blocks))

    def test_image_kind_requires_actual_image_and_its_grounding(self):
        image = self.image_proposal()
        self.assertEqual(validate_proposal(image, self.blocks), image)
        for proposal in ({**image, "image_block_id": None},
                         {**image, "image_block_id": "p0-b1"},
                         {**image, "block_ids": ["p0-b1"]},
                         {**self.proposal, "image_block_id": "p0-b2"}):
            self.assert_invalid(lambda: validate_proposal(proposal, self.blocks))
        blocks = deepcopy(self.blocks)
        blocks["p0-b2"]["image_paths"] = []
        self.assert_invalid(lambda: validate_proposal(image, blocks))

    def test_image_artifact_metadata_requires_relative_path_and_digest(self):
        for artifact in ({"path": "../escape.png", "sha256": "a" * 64},
                         {"path": "/absolute.png", "sha256": "a" * 64},
                         {"path": "C:\\absolute.png", "sha256": "a" * 64},
                         {"path": "images/figure.png", "sha256": "invalid"}):
            blocks = deepcopy(self.blocks)
            blocks["p0-b2"]["image_paths"] = [artifact]
            with self.subTest(artifact=artifact):
                self.assert_invalid(lambda: validate_proposal(self.image_proposal(), blocks))

    def test_image_modality_accepts_real_chart_and_table_crops_without_changing_source_types(self):
        for source_type in ("image", "chart", "table"):
            with self.subTest(source_type=source_type):
                blocks = deepcopy(self.blocks)
                blocks["p0-b2"]["type"] = source_type
                before = deepcopy(blocks)
                normalized = validate_proposal(self.image_proposal(), blocks)
                self.assertEqual(normalized["kind"], "image")
                self.assertEqual(blocks, before)
                self.assertRegex(fingerprints(self.data_id, normalized, blocks)["content_fingerprint"], r"^[0-9a-f]{64}$")
                blocks["p0-b2"]["image_paths"] = []
                self.assert_invalid(lambda: validate_proposal(self.image_proposal(), blocks))
        for source_type in ("text", "title", "chart_caption", "unknown"):
            blocks = deepcopy(self.blocks)
            blocks["p0-b2"]["type"] = source_type
            self.assert_invalid(lambda: validate_proposal(self.image_proposal(), blocks))

    def test_structural_validity_does_not_claim_source_fidelity(self):
        false_statement = {**self.proposal, "content": "The sample contains 999 observations."}
        self.assertEqual(validate_proposal(false_statement, self.blocks)["content"], false_statement["content"])
        # Only the real semantic Validator can reject the false statement.
        decisions = validate_decisions([self.decision(verdict="rejected")], 1)
        self.assertEqual(decisions[0]["verdict"], "rejected")

    def test_fingerprints_separate_data_identity_from_exact_semantic_content(self):
        first = fingerprints(self.data_id, self.proposal, self.blocks)
        other = fingerprints(sha256(b"another PDF").hexdigest(), self.proposal, self.blocks)
        self.assertNotEqual(first["identity_fingerprint"], other["identity_fingerprint"])
        self.assertEqual(first["content_fingerprint"], other["content_fingerprint"])
        self.assertNotEqual(first["context_fingerprint"], other["context_fingerprint"])
        for value in first.values():
            self.assertRegex(value, r"^[0-9a-f]{64}$")
        self.assert_invalid(lambda: fingerprints("wrong Data ID", self.proposal, self.blocks))

    def test_display_title_changes_only_context_not_semantic_fingerprints(self):
        first = fingerprints(self.data_id, self.proposal, self.blocks)
        renamed = fingerprints(self.data_id, {**self.proposal, "title": "A different display title"}, self.blocks)
        self.assertEqual(first["identity_fingerprint"], renamed["identity_fingerprint"])
        self.assertEqual(first["content_fingerprint"], renamed["content_fingerprint"])
        self.assertNotEqual(first["context_fingerprint"], renamed["context_fingerprint"])

    def test_anchor_or_meaning_changes_affect_identity(self):
        first = fingerprints(self.data_id, self.proposal, self.blocks)
        blocks = deepcopy(self.blocks)
        blocks["p0-b1"]["anchor_sha256"] = sha256(b"corrected anchor").hexdigest()
        corrected = fingerprints(self.data_id, self.proposal, blocks)
        self.assertNotEqual(first["identity_fingerprint"], corrected["identity_fingerprint"])
        self.assertEqual(first["content_fingerprint"], corrected["content_fingerprint"])
        changed = fingerprints(self.data_id, {**self.proposal, "content": "A different meaning."}, self.blocks)
        self.assertNotEqual(first["identity_fingerprint"], changed["identity_fingerprint"])
        self.assertNotEqual(first["content_fingerprint"], changed["content_fingerprint"])

    def test_opaque_parser_refs_and_numeric_representation_do_not_change_identity(self):
        first = fingerprints(self.data_id, self.proposal, self.blocks)
        block = deepcopy(self.blocks["p0-b1"])
        block.update(block_id="renamed-block", raw_locator="/new/output/0", parser_execution_id="opaque-run")
        block["bbox"] = [float(value) for value in block["bbox"]]
        block["page_size"] = [float(value) for value in block["page_size"]]
        proposal = {**self.proposal, "block_ids": ["renamed-block"]}
        second = fingerprints(self.data_id, proposal, {"renamed-block": block})
        self.assertEqual(first["identity_fingerprint"], second["identity_fingerprint"])
        self.assertEqual(first["content_fingerprint"], second["content_fingerprint"])
        self.assertNotEqual(first["context_fingerprint"], second["context_fingerprint"])

    def test_image_bytes_are_part_of_semantic_content(self):
        image = self.image_proposal()
        first = fingerprints(self.data_id, image, self.blocks)
        blocks = deepcopy(self.blocks)
        blocks["p0-b2"]["image_paths"][0]["sha256"] = sha256(b"different image").hexdigest()
        second = fingerprints(self.data_id, image, blocks)
        self.assertNotEqual(first["identity_fingerprint"], second["identity_fingerprint"])
        self.assertNotEqual(first["content_fingerprint"], second["content_fingerprint"])

    def test_validation_decisions_require_exact_coverage_and_preserve_verdicts(self):
        decisions = [self.decision(2, "needs_human"), self.decision(0), self.decision(1, "rejected")]
        before = deepcopy(decisions)
        result = validate_decisions(decisions, 3)
        self.assertEqual(set(result), {0, 1, 2})
        self.assertEqual(result[2]["verdict"], "needs_human")
        self.assertEqual(result[1]["verdict"], "rejected")
        self.assertEqual(decisions, before)
        self.assertEqual(validate_decisions([], 0), {})

    def test_missing_duplicate_out_of_range_and_boolean_ordinals_fail(self):
        for decisions, count in (([], 1), ([self.decision(), self.decision()], 2),
                                 ([self.decision(1)], 1), ([self.decision(-1)], 1),
                                 ([self.decision(True)], 1), ([self.decision()], True),
                                 ([], -1), ({"decisions": []}, 0)):
            with self.subTest(decisions=decisions, count=count):
                self.assert_invalid(lambda: validate_decisions(decisions, count), "invalid_validation")

    def test_validation_rejects_extra_missing_or_malformed_fields(self):
        decision = self.decision()
        cases = [{**decision, "chain_of_thought": "not part of this contract"},
                 {k: v for k, v in decision.items() if k != "reason"}]
        for field, value in (("verdict", "approved"), ("reason", " "), ("reason", "\ud800"),
                             ("reason_codes", "not a list"), ("reason_codes", [None])):
            cases.append({**decision, field: value})
        for value in cases:
            with self.subTest(decision=repr(value)):
                self.assert_invalid(lambda: validate_decisions([value], 1), "invalid_validation")

    def test_reason_codes_are_bounded_classifications_not_normalized_prose(self):
        decision = self.decision()
        for invalid in ("Source_Fidelity", "source fidelity", "source-fidelity", " source_fidelity ",
                        "source_fidelity\n", "기각 원문", "a" * 65, "", None):
            with self.subTest(code=invalid):
                self.assert_invalid(lambda: validate_decisions(
                    [{**decision, "reason_codes": [invalid]}], 1), "invalid_validation")
        for valid in ([], ["a"], ["source_fidelity", "missing_context_2"], ["a" * 64]):
            self.assertEqual(validate_decisions([{**decision, "reason_codes": valid}], 1)[0]["reason_codes"], valid)


if __name__ == "__main__":
    unittest.main()
