"""Exact source spans and conservative caption/Figure lookup associations."""

from copy import deepcopy
import unittest

from palimpsest.figure_references import extract_caption_anchors, extract_figure_mentions


class FigureReferenceTests(unittest.TestCase):
    @staticmethod
    def block(text, kind="text"):
        return {"block_id": "/b/4", "raw_locator": "/pdf_info/8/preproc_blocks/4",
                "page_index": 8, "bbox": [12, 18, 400, 600], "type": kind,
                "text": text, "children": [], "segments": []}

    def keys(self, text):
        values = extract_figure_mentions(text)
        for item in values:
            self.assertEqual(text[item["char_start"]:item["char_end"]], item["text"])
        return [(item["scope"], item["number"], item["panels"]) for item in values]

    def test_common_labels_multiple_mentions_and_exact_unicode_offsets(self):
        text = "μ signal: Fig. 1 shows a result; see Figures 2 and 3, and FIG. 4A."
        self.assertEqual(self.keys(text), [("main", "1", []), ("main", "2", []),
                                          ("main", "3", []), ("main", "4", ["a"])])
        self.assertEqual(extract_figure_mentions(text), extract_figure_mentions(text))
        self.assertEqual(self.keys("configuration 2 and disfigure 1; Fig. X, Fig. 1word"), [])

    def test_ranges_lists_supplement_and_panels(self):
        cases = {
            "Figs. 1–3, 5 and 7": [("main", n, []) for n in ("1", "2", "3", "5", "7")],
            "Supplementary Figures 1 and 2": [("supplement", "1", []), ("supplement", "2", [])],
            "Figs. S1-S3": [("supplement", n, []) for n in ("1", "2", "3")],
            "Fig.1; Supp. Fig. S2": [("main", "1", []), ("supplement", "2", [])],
            "Figure 1A–C, E": [("main", "1", ["a", "b", "c", "e"])],
            "Fig. 2(a–c) and 3(d, e)": [("main", "2", ["a", "b", "c"]), ("main", "3", ["d", "e"])],
            "Fig. 2, A and B": [("main", "2", ["a", "b"])],
            "Fig. 1 and a later experiment": [("main", "1", [])],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.keys(text), expected)

    def test_unexpanded_ranges_are_explicit_not_silent_partial_links(self):
        for text in ("Figures 5–2", "Figures 1–999999999", "Figures 1–S2", "Figures 1a–3c"):
            with self.subTest(text=text):
                result = extract_figure_mentions(text)
                self.assertEqual(len(result), 2)
                self.assertTrue(all("figure_range_not_expanded" in item["warnings"] for item in result))
                self.assertTrue(all(item["text"] == text for item in result))
        self.assertIn("panel_range_not_expanded", extract_figure_mentions("Fig. 1c–a")[0]["warnings"])

    def test_body_callouts_are_not_caption_anchors(self):
        for text in ("Fig. 1 shows the result.", "Figure 2 was imaged.",
                     "As shown in Fig. 3. This is body prose.", "Fig. 1, unlike Fig. 2, is positive."):
            with self.subTest(text=text):
                self.assertEqual(extract_caption_anchors(self.block(text)), [])

    def test_caption_only_uses_its_prefix_and_keeps_whole_exact_source_text(self):
        block = self.block("  Fig. 3. Results are compared with Fig. 8 and Figure 9.\n")
        before = deepcopy(block)
        anchors = extract_caption_anchors(block)
        self.assertEqual(len(anchors), 1)
        anchor = anchors[0]
        self.assertEqual((anchor["scope"], anchor["number"]), ("main", "3"))
        self.assertEqual(anchor["text"], block["text"][anchor["char_start"]:anchor["char_end"]])
        self.assertEqual(anchor["source_block_id"], block["block_id"])
        self.assertEqual(anchor["raw_locator"], block["raw_locator"])
        self.assertEqual(anchor["page_index"], 8)
        self.assertFalse(anchor["is_continuation"])
        anchor["bbox"][0] = 0
        self.assertEqual(block, before)

    def test_continued_prefix_is_explicit_even_without_caption_type(self):
        for text in ("Fig. 4 continued", "Figure 3. (continued)", "FIG. 5 (Continued). More caption."):
            with self.subTest(text=text):
                anchors = extract_caption_anchors(self.block(text))
                self.assertEqual(len(anchors), 1)
                self.assertTrue(anchors[0]["is_continuation"])
                self.assertEqual(anchors[0]["continuation_basis"], "explicit_continuation_marker")
        self.assertFalse(extract_caption_anchors(self.block("Figure 3. Treatment continued for 4 days."))[0]["is_continuation"])

    def test_explicit_caption_type_supports_missing_separator_and_supplement(self):
        result = extract_caption_anchors(self.block("Supplementary Fig. S2 Signal intensity", "image_caption"))
        self.assertEqual([(item["scope"], item["number"]) for item in result], [("supplement", "2")])
        self.assertEqual(result[0]["recognition_basis"], "explicit_caption_type_and_prefix")

    def test_child_caption_keeps_exact_leaf_refs_and_does_not_claim_block_offsets(self):
        block = self.block("Parser image wrapper with Fig. 9.", "image")
        child_ref = block["raw_locator"] + "/blocks/1"
        block["children"] = [{"type": "image_caption", "raw_locator": child_ref, "bbox": [1, 2, 30, 40]}]
        block["segments"] = [
            {"raw_locator": child_ref + "/lines/0/spans/0", "content": "Figure 2.", "bbox": [2, 3, 20, 5]},
            {"raw_locator": child_ref + "/lines/1/spans/0", "content": "Compared with Fig. 7."},
            {"raw_locator": child_ref + "0/lines/0/spans/0", "content": "Figure 8."},
        ]
        before = deepcopy(block)
        result = extract_caption_anchors(block)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["number"], "2")
        self.assertEqual(result[0]["raw_locator"], child_ref)
        self.assertIsNone(result[0]["char_start"])
        self.assertIsNone(result[0]["char_end"])
        self.assertEqual([item["text"] for item in result[0]["segment_refs"]], ["Figure 2.", "Compared with Fig. 7."])
        result[0]["segment_refs"][0]["bbox"][0] = 0
        self.assertEqual(block, before)


if __name__ == "__main__":
    unittest.main()
