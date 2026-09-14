"""Deterministic dual-transcription selection, without models or storage."""
from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.transcription_selection import select_transcription


class TranscriptionSelectionTests(unittest.TestCase):
    source = {"artifact_path": "ocr/source_middle.json", "sha256": "a" * 64}

    def bundle(self, text, *, channel="native", segments=None, page=0):
        locator = f"/pdf_info/{page}/preproc_blocks/0"
        if segments is None:
            segments = [{"type": "text", "raw_locator": locator + "/lines/0/spans/0",
                         "bbox": [10, 10, 300, 40], "content": text}]
        return {"schema_version": 1, "data_id": "d" * 64, "coordinate_system": "pdf_points_top_left",
            "pages": [{"page_index": page, "page_size": [600, 800]}],
            "blocks": [{"block_id": locator, "raw_locator": locator, "page_index": page,
                "page_size": [600, 800], "bbox": [10, 10, 300, 40], "text": text,
                "type": "text", "segments": segments, "raw_block_sha256": sha256((channel+text).encode()).hexdigest()}]}

    def select(self, native, ocr):
        return select_transcription(self.bundle(native), self.bundle(ocr, channel="ocr"), ocr_source=self.source)

    def assert_selected(self, native, ocr, expected):
        projection = self.select(native, ocr)
        self.assertEqual(projection["status"], "complete", projection["unresolved"])
        self.assertEqual(projection["blocks"][0]["selected_text"], expected)
        return projection["blocks"][0]

    def test_greek_micro_patch_retains_ordinary_native_digits_and_letters(self):
        row = self.assert_selected("C1q used 1 mM FBG in cells.", r"Clq used 1 \mu M FBG in cells.", "C1q used 1 μM FBG in cells.")
        self.assertEqual(len(row["changes"]), 1)
        self.assertEqual(row["changes"][0]["native_text"], "m")
        self.assertEqual(row["changes"][0]["ocr_text"], r"\mu")
        self.assertEqual(row["ordinary_differences"][0]["decision"], "native_ordinary_preferred")
        change = row["changes"][0]
        self.assertEqual(change["native_range"], [11, 12])
        self.assertEqual(change["ocr_refs"][0]["character_range"], [11, 14])
        self.assertEqual(change["ocr_refs"][0]["field_locator"], "/pdf_info/0/preproc_blocks/0/lines/0/spans/0/content")
        self.assertEqual(change["selected_range"], [11, 12])
        self.assertEqual(change["ocr_refs"][0]["raw_artifact"], self.source)

    def test_phi_and_hyphen_loss_in_same_block_do_not_replace_ordinary_text(self):
        self.assert_selected("Mf-mediated OVA-RMA cells were used.", "Mφ-mediated OVARMA cells were used.", "Mφ-mediated OVA-RMA cells were used.")

    def test_existing_greek_prefers_aligned_ocr_greek_or_ascii(self):
        self.assert_selected("TGF-α1 promotes growth.", "TGF-β1 promotes growth.", "TGF-β1 promotes growth.")
        row = self.assert_selected("TGF-β1 promotes growth.", "TGF-b1 promotes growth.", "TGF-b1 promotes growth.")
        self.assertEqual(row["changes"][0]["reason"], "ocr_ascii_over_native_special")

    def test_source_control_glyph_can_be_replaced_by_bound_ocr_greek(self):
        row = self.assert_selected("The Fc\x01RIIA receptor binds IC.", "The FcγRIIA receptor binds IC.", "The FcγRIIA receptor binds IC.")
        self.assertEqual(row["changes"][0]["native_text"], "\x01")

    def test_explicit_scripts_allow_script_digits_but_keep_ordinary_digits(self):
        self.assert_selected("IL12 with sample 123 was measured.", "IL_{17} with sample 128 was measured.", "IL<sub>17</sub> with sample 123 was measured.")
        self.assert_selected("CD4+ T cells were used.", "CD4^{+} T cells were used.", "CD4<sup>+</sup> T cells were used.")
        self.assert_selected("CD4+ T cells were used.", "CD4⁺ T cells were used.", "CD4⁺ T cells were used.")

    def test_identical_ordinary_identifiers_urls_carets_and_braced_literals_stay_exact(self):
        for text in ("The key is sample_id in this table.", "https://example.org/foo_bar",
                     "The operator is a^b in code.", "The key is sample_{id} in this table."):
            with self.subTest(text=text):
                row = self.assert_selected(text, text, text)
                self.assertEqual(row["changes"], [])
                self.assertEqual(row["issues"], [])

    def test_ordinary_identifier_differences_keep_native_without_script_invention(self):
        self.assert_selected("Use sample_id and https://example.org/foo_bar.",
                             "Use sample_jd and https://example.org/foo_car.",
                             "Use sample_id and https://example.org/foo_bar.")

    def test_shorthand_requires_equation_leaf_latex_field_or_closed_math_delimiters(self):
        for ocr in ("A value $x^2$ was used.", "A value $$x^2$$ was used.",
                    r"A value \(x^2\) was used.", r"A value \[x^2\] was used."):
            with self.subTest(ocr=ocr):
                self.assert_selected("A value x2 was used.", ocr, "A value x<sup>2</sup> was used.")
        self.assert_selected("A value x2 was used.", "A value x^2 was used.", "A value x2 was used.")
        for field in ("content", "latex"):
            native = self.bundle("A value x2 was used.")
            ocr = self.bundle("A value x^2 was used.", channel="ocr")
            segment = ocr["blocks"][0]["segments"][0]
            segment["type"] = "inline_equation" if field == "content" else "text"
            if field == "latex":
                segment[field] = segment.pop("content")
            row = select_transcription(native, ocr, ocr_source=self.source)["blocks"][0]
            self.assertEqual(row["selected_text"], "A value x<sup>2</sup> was used.")

    def test_operator_and_limited_math_wrapper_use_explicit_rendering(self):
        self.assert_selected("A dose is 1 mg/ml and x = 2.", r"A dose is 1 \mu \mathrm{g/ml} and x \leq 2.", "A dose is 1 μg/ml and x ≤ 2.")

    def test_missing_micro_has_zero_width_native_interval_with_anchor_provenance(self):
        row = self.assert_selected("Use 3 M TAK-242 in cells.", "Use 3 μM TAK-242 in cells.", "Use 3 μM TAK-242 in cells.")
        change = row["changes"][0]
        self.assertEqual(change["native_range"], [6, 6])
        self.assertEqual(change["native_refs"], [])
        self.assertTrue(change["native_anchor_refs"])

    def test_missing_beta_inserts_before_native_gap_and_preserves_all_whitespace(self):
        native = "injection of recombinant TGF- in addition to recombinant"
        ocr = "injection of recombinant TGF-β in addition to recombinant"
        row = self.assert_selected(native, ocr, ocr)
        self.assertEqual(row["changes"][0]["native_range"], [29, 29])
        self.assertEqual(row["changes"][0]["selected_range"], [29, 30])
        self.assert_selected("TGF-\r\n  in addition", "TGF-β in addition", "TGF-β\r\n  in addition")
        self.assert_selected("Use 1 \t M here.", "Use 1 μM here.", "Use 1 \t μM here.")

    def test_missing_special_with_both_ocr_gaps_or_conflicting_adjacency_is_unresolved(self):
        for native, ocr in (("Use 3 M here.", r"Use 3 \mu M here."),
                            ("TGF- in addition", "TGF- β in addition"),
                            ("TGF- in addition", "TGF-βin addition")):
            with self.subTest(native=native, ocr=ocr):
                row = self.select(native, ocr)["blocks"][0]
                self.assertEqual(row["status"], "needs_review")
                self.assertEqual(row["selected_text"], native)
                self.assertEqual(row["changes"], [])

    def test_missing_special_prefix_and_suffix_preserve_native_edge_whitespace(self):
        self.assert_selected("  M solution was used.", "  μM solution was used.", "  μM solution was used.")
        self.assert_selected("M solution was used.", "μM solution was used.", "μM solution was used.")
        self.assert_selected("The cytokine is TGF-  ", "The cytokine is TGF-β  ", "The cytokine is TGF-β  ")
        self.assert_selected("The cytokine is TGF-", "The cytokine is TGF-β", "The cytokine is TGF-β")
        self.assert_selected("CD4  ", "CD4^{+}  ", "CD4<sup>+</sup>  ")

    def test_split_raw_equation_leaf_preserves_exact_field_interval_and_geometry(self):
        base = "/pdf_info/0/preproc_blocks/0/lines/0/spans/"
        values = [("Dose 1", "text"), (r"\mu", "inline_equation"), ("M FBG is used.", "text")]
        segments = [{"type": kind, "raw_locator": base+str(index), "bbox": [10, 10, 300, 40],
                     "raw_bbox": [9, 10, 299, 40], "content": value}
                    for index, (value, kind) in enumerate(values)]
        native = self.bundle("Dose 1 mM FBG is used.")
        ocr = self.bundle(r"Dose 1 \mu M FBG is used.", channel="ocr", segments=segments)
        row = select_transcription(native, ocr, ocr_source=self.source)["blocks"][0]
        self.assertEqual(row["selected_text"], "Dose 1 μM FBG is used.")
        reference = row["changes"][0]["ocr_refs"][0]
        self.assertEqual(reference["raw_locator"], base+"1")
        self.assertEqual(reference["character_range"], [0, 3])
        self.assertEqual(reference["raw_bbox"], [9, 10, 299, 40])

    def test_duplicate_spatial_context_is_unresolved_and_does_not_pick_by_score(self):
        native, ocr = self.bundle("Use 1 mM here."), self.bundle("Use 1 μM here.", channel="ocr")
        duplicate = deepcopy(ocr["blocks"][0]); duplicate["block_id"] += "/duplicate"
        ocr["blocks"].append(duplicate)
        result = select_transcription(native, ocr, ocr_source=self.source)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["blocks"][0]["selected_text"], "Use 1 mM here.")
        self.assertIn("ambiguous_block_alignment", result["blocks"][0]["issues"])
        self.assertEqual(len(result["unmatched_ocr_blocks"]), 2)

    def test_extra_ocr_text_and_image_inventory_is_never_silently_dropped(self):
        native, ocr = self.bundle("Source text."), self.bundle("Source text.", channel="ocr")
        extra = deepcopy(ocr["blocks"][0]); extra.update(block_id="/extra", bbox=[400, 100, 590, 140])
        extra["image_paths"] = [{"path": "ocr/image.png", "sha256": "a"*64}]
        ocr["blocks"].append(extra)
        result = select_transcription(native, ocr, ocr_source=self.source)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["unmatched_ocr_block_ids"], ["/extra"])
        self.assertTrue(result["unmatched_ocr_blocks"][0]["has_visual"])

    def test_reusing_ocr_region_for_two_native_blocks_is_unresolved(self):
        native, ocr = self.bundle("Use 1 mM here."), self.bundle("Use 1 μM here.", channel="ocr")
        duplicate = deepcopy(native["blocks"][0]); duplicate["block_id"] += "/duplicate"
        native["blocks"].append(duplicate)
        result = select_transcription(native, ocr, ocr_source=self.source)
        self.assertEqual(len(result["unresolved"]), 2)
        self.assertTrue(all(not row["changes"] for row in result["blocks"]))

    def test_mixed_ordinary_and_special_difference_does_not_replace_a_phrase(self):
        result = self.select("Sample MfX was used.", "Sample MφY was used.")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["blocks"][0]["selected_text"], "Sample MfX was used.")

    def test_ambiguous_block_defers_other_safe_changes_in_the_same_block(self):
        native = "Dose 1 mM and MfX cells."
        result = self.select(native, "Dose 1 μM and MφY cells.")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["blocks"][0]["selected_text"], native)
        self.assertEqual(result["blocks"][0]["changes"], [])

    def test_unknown_latex_is_unresolved_without_partial_repair(self):
        result = self.select("Dose 1 mM equals x/y.", r"Dose 1 \mu M equals \frac{x}{y}.")
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("unsupported_latex_macro", result["blocks"][0]["issues"])
        self.assertEqual(result["blocks"][0]["selected_text"], "Dose 1 mM equals x/y.")

    def test_no_cross_page_or_nonoverlapping_region_match(self):
        native, ocr = self.bundle("Use 1 mM here."), self.bundle("Use 1 μM here.", channel="ocr")
        ocr["blocks"][0]["bbox"] = [400, 100, 590, 140]
        result = select_transcription(native, ocr, ocr_source=self.source)
        self.assertEqual(result["blocks"][0]["issues"], ["unmatched_block"])

    def test_invalid_original_identity_geometry_raw_mapping_and_controls_fail(self):
        for mutation in (
            lambda b: b.update(data_id="e"*64),
            lambda b: b["pages"][0].update(page_size=[601, 800]),
            lambda b: b["blocks"][0].update(text="Different unbound text"),
            lambda b: b["blocks"][0].update(text="PRIVATE\x00invalid"),
        ):
            native, ocr = self.bundle("Use 1 mM here."), self.bundle("Use 1 μM here.", channel="ocr")
            mutation(ocr)
            with self.assertRaises(PalimpsestError) as caught:
                select_transcription(native, ocr, ocr_source=self.source)
            self.assertEqual(caught.exception.code, "invalid_transcription_selection")
            self.assertNotIn("PRIVATE", json.dumps(caught.exception.details))

    def test_replay_is_deterministic_and_inputs_and_returned_metadata_are_independent(self):
        native, ocr = self.bundle("Mf-mediated cells."), self.bundle("Mφ-mediated cells.", channel="ocr")
        before = deepcopy((native, ocr, self.source))
        first = select_transcription(native, ocr, ocr_source=self.source)
        self.assertEqual(first, select_transcription(native, ocr, ocr_source=self.source))
        first["ocr_source"]["artifact_path"] = "changed"
        first["blocks"][0]["alignment"]["ocr_refs"][0]["bbox"][0] = 900
        self.assertEqual((native, ocr, self.source), before)


if __name__ == "__main__":
    unittest.main()
