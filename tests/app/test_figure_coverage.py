"""Pure Figure coverage checks; no parser, model, filesystem, or DB claims."""

from copy import deepcopy
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.figure_coverage import figure_coverage


class FigureCoverageTests(unittest.TestCase):
    def setUp(self):
        self.bundle = {"blocks": [], "required_figures": [], "extraction_scope": "figures_only"}
        self.proposals = []
        for number in range(1, 7):
            primary = f"/figures/{number - 1}"
            members = [f"/page/{number}/panel/A", f"/page/{number}/panel/B"]
            captions = [f"/page/{number}/caption", f"/page/{number + 1}/continuation"]
            self.bundle["blocks"].append({"block_id": primary, "type": "image",
                                         "image_paths": [{"path": f"figures/{number}.png"}]})
            self.bundle["blocks"].extend({"block_id": item, "type": "text"}
                                         for item in members + captions)
            self.bundle["required_figures"].append({"figure_id": f"figure:{number}", "number": number,
                "block_id": primary, "member_block_ids": members, "caption_block_ids": captions})
            self.proposals.append({"kind": "image", "semantic_type": "figure",
                "title": "PRIVATE_TITLE", "content": "PRIVATE_CONTENT",
                "image_block_id": primary, "block_ids": [primary] + members + captions})
        self.decisions = [{"ordinal": index, "verdict": "accepted",
                           "reason_codes": ["source_fidelity"], "reason": "PRIVATE_REASON"}
                          for index in range(6)]

    def assert_incomplete(self, bundle, proposals):
        with self.assertRaises(PalimpsestError) as caught:
            figure_coverage(bundle, proposals)
        self.assertEqual(caught.exception.code, "incomplete_figure_coverage")
        self.assertEqual(caught.exception.exit_code, 4)
        self.assertNotIn("PRIVATE_", json.dumps(caught.exception.details))

    def test_inventory_and_structure_do_not_claim_semantic_completion(self):
        before = deepcopy((self.bundle, self.proposals))
        self.assertEqual(figure_coverage(self.bundle, None)["status"], "pending_generation")
        ledger = figure_coverage(self.bundle, self.proposals)
        self.assertEqual(ledger["status"], "pending_validation")
        self.assertEqual(ledger["required_count"], 6)
        self.assertEqual([item["ordinal"] for item in ledger["figures"]], list(range(6)))
        self.assertTrue(all(item["verdict"] is None for item in ledger["figures"]))
        self.assertEqual((self.bundle, self.proposals), before)

    def test_each_figure_must_appear_even_when_total_count_is_six(self):
        self.assert_incomplete(self.bundle, self.proposals[:3] + self.proposals[4:])
        same_count = deepcopy(self.proposals)
        same_count[3] = deepcopy(same_count[2])
        self.assert_incomplete(self.bundle, same_count)
        self.assert_incomplete(self.bundle, self.proposals + [self.proposals[0]])

    def test_every_primary_panel_and_cross_page_caption_reference_is_required(self):
        for missing in self.proposals[4]["block_ids"]:
            with self.subTest(missing=missing):
                proposals = deepcopy(self.proposals)
                proposals[4]["block_ids"].remove(missing)
                self.assert_incomplete(self.bundle, proposals)
        proposals = deepcopy(self.proposals)
        proposals[4]["image_block_id"] = self.bundle["required_figures"][4]["member_block_ids"][0]
        self.assert_incomplete(self.bundle, proposals)

    def test_figures_only_rejects_unrelated_images_and_text_while_general_scope_preserves_them(self):
        extra = {"kind": "text", "semantic_type": "observation", "image_block_id": None,
                 "block_ids": [self.bundle["required_figures"][0]["member_block_ids"][0]]}
        self.assert_incomplete(self.bundle, self.proposals + [extra])
        extra_image = {**extra, "kind": "image", "image_block_id": extra["block_ids"][0]}
        self.assert_incomplete(self.bundle, self.proposals + [extra_image])
        self.bundle["extraction_scope"] = "whole_document"
        ledger = figure_coverage(self.bundle, [extra] + self.proposals)
        self.assertEqual([item["ordinal"] for item in ledger["figures"]], list(range(1, 7)))
        for kind, semantic_type in (("text", "figure"), ("image", "observation")):
            proposals = deepcopy(self.proposals)
            proposals[0].update(kind=kind, semantic_type=semantic_type)
            self.assert_incomplete(self.bundle, proposals)

    def test_semantic_verdicts_control_completion_and_remain_unchanged_without_bodies(self):
        ledger = figure_coverage(self.bundle, self.proposals, list(reversed(self.decisions)))
        self.assertEqual(ledger["status"], "complete")
        self.decisions[3]["verdict"] = "rejected"
        self.decisions[4]["verdict"] = "needs_human"
        before = deepcopy(self.decisions)
        ledger = figure_coverage(self.bundle, self.proposals, self.decisions)
        self.assertEqual(ledger["status"], "incomplete")
        self.assertEqual(ledger["figures"][3]["verdict"], "rejected")
        self.assertEqual(ledger["figures"][4]["verdict"], "needs_human")
        self.assertEqual(self.decisions, before)
        self.assertNotIn("PRIVATE_", json.dumps(ledger))

    def test_decision_ordinal_coverage_cannot_silently_imply_acceptance(self):
        for decisions in (self.decisions[:-1], self.decisions + [self.decisions[0]]):
            with self.assertRaises(PalimpsestError) as caught:
                figure_coverage(self.bundle, self.proposals, decisions)
            self.assertEqual(caught.exception.code, "invalid_validation")

    def test_inventory_rejects_unknown_duplicate_and_invalid_primary_references_before_generation(self):
        cases = []
        for field, value in (("figure_id", "figure:2"), ("number", 2),
                             ("block_id", "/figures/1"), ("member_block_ids", ["unknown"]),
                             ("caption_block_ids", ["unknown"]), ("number", True),
                             ("member_block_ids", []), ("caption_block_ids", ["/figures/0"])):
            bundle = deepcopy(self.bundle)
            bundle["required_figures"][0][field] = value
            cases.append(bundle)
        for value in ([], None):
            bundle = deepcopy(self.bundle)
            bundle["blocks"][0]["image_paths"] = value
            cases.append(bundle)
        bundle = deepcopy(self.bundle)
        bundle["blocks"].append(deepcopy(bundle["blocks"][0]))
        cases.append(bundle)
        for index, bundle in enumerate(cases):
            with self.subTest(case=index):
                self.assert_incomplete(bundle, None)

    def test_no_inventory_keeps_generic_extraction_but_cannot_hide_a_figures_only_scope(self):
        self.assertEqual(figure_coverage({}, []),
                         {"status": "not_required", "required_count": 0, "figures": []})
        self.assert_incomplete({"extraction_scope": "figures_only"}, None)
        self.assert_incomplete({"required_figures": None}, None)


if __name__ == "__main__":
    unittest.main()
