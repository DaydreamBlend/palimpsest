"""Page reading projections preserve source I; no database, parser, or model call."""

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.page_projection import build_pages, select_page_context
from palimpsest.source_units import build_source_units


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class PageProjectionTests(unittest.TestCase):
    def setUp(self):
        self.bundle = {
            "schema_version": 1, "data_id": "b" * 64,
            "coordinate_system": "pdf_points_top_left", "extraction_scope": "whole_document",
            "pages": [{"page_index": page, "page_size": [600, 800]} for page in range(4)],
            "blocks": [
                self.block("/body", 0, 3, "  본문 Cafe\u0301\r\n"),
                self.block("/header", 0, 1, " Journal ", "header", "discarded_blocks"),
                self.block("/panel", 1, 2, "", "chart", image="panel.png"),
                self.block("/caption", 1, 3, "Figure 1. PRIVATE_CAPTION"),
                self.block("/second", 1, 1, "Before figure"),
                self.block("/continuation", 2, 1, "  PRIVATE_CONTINUATION  "),
                self.block("/third", 2, 2, "Third page"),
                self.block("/empty", 3, 1, ""),
                self.block("/figures/0", 1, None, "SYNTHETIC_DISPLAY_LABEL", "image",
                           "original_pdf_figure_regions", image="full.png"),
            ],
            "required_figures": [{"figure_id": "figure:1", "number": 1,
                "block_id": "/figures/0", "member_block_ids": ["/panel"],
                "caption_block_ids": ["/caption", "/continuation"]}],
        }
        self.rows = self.source_rows(self.bundle)
        self.figure_id = next(row["information_id"] for row in self.rows if row["unit_type"] == "figure")

    @staticmethod
    def block(ref, page, index, text, kind="text", collection="preproc_blocks", image=None):
        return {"block_id": ref, "type": kind, "page_index": page,
            "page_size": [600, 800], "bbox": [10, 20, 300, 100],
            "text": text, "raw_locator": ref, "source_collection": collection,
            "upstream_metadata": {"index": index} if index is not None else {},
            "anchor_sha256": sha256(ref.encode()).hexdigest(),
            "supported": True, "unsupported": [], "empty": not text and not image,
            "image_paths": [{"path": "images/" + image, "sha256": sha256(image.encode()).hexdigest()}]
                           if image else []}

    @staticmethod
    def source_rows(bundle):
        by_id = {block["block_id"]: block for block in bundle["blocks"]}
        artifacts = {image["path"]: {"artifact_path": "objects/sha256/" + image["sha256"],
                     "sha256": image["sha256"], "byte_size": 123}
                     for block in bundle["blocks"] for image in block["image_paths"]}
        rows = []
        for ordinal, proposal in enumerate(build_source_units(bundle)):
            primary = proposal["image_block_id"]
            source_blocks = [deepcopy(by_id[ref]) for ref in proposal["block_ids"]]
            rows.append({"information_id": f"I{ordinal + 1}", "data_id": bundle["data_id"],
                **{key: proposal[key] for key in ("kind", "semantic_type", "unit_type", "title", "content")},
                "payload": {"schema_version": "source-information-v1", "semantic_checked": False,
                    "validation_basis": "source_structure", "empty_content": proposal["content"] == "",
                    "source_bundle_sha256": digest(bundle), "primary_block_id": primary,
                    "source_blocks": source_blocks,
                    "images": [deepcopy(artifacts[image["path"]]) for image in by_id[primary]["image_paths"]]
                              if primary else [],
                    "source_artifacts": {image["path"]: deepcopy(artifacts[image["path"]])
                                         for block in source_blocks for image in block["image_paths"]}}})
        return rows

    def assert_error(self, code, operation):
        with self.assertRaises(PalimpsestError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn("PRIVATE_", json.dumps(caught.exception.details))

    def test_reading_order_is_mineru_index_including_discarded_headers(self):
        projection = build_pages(self.bundle, self.rows)
        self.assertEqual(projection["schema_version"], "source-pages-v1")
        self.assertEqual(projection["data_id"], self.bundle["data_id"])
        self.assertEqual(projection["source_bundle_sha256"], digest(self.bundle))
        self.assertEqual([page["page_number"] for page in projection["pages"]], [1, 2, 3, 4])
        first = projection["pages"][0]
        self.assertEqual([block["block_id"] for block in first["blocks"]], ["/header", "/body"])
        self.assertEqual(first["content"], " Journal \n\n  본문 Cafe\u0301\r\n")
        self.assertEqual(first["blocks"][0]["source_collection"], "discarded_blocks")
        self.assertEqual(first["blocks"][0]["mineru_index"], 1)

    def test_text_offsets_are_exact_unicode_codepoint_ranges_including_empty_blocks(self):
        projection = build_pages(self.bundle, self.rows)
        originals = {block["block_id"]: block for block in self.bundle["blocks"]}
        mapped = []
        for page in projection["pages"]:
            self.assertEqual(page["page_index"], page["page_number"] - 1)
            self.assertEqual(page["page_size"], [600, 800])
            for item in page["blocks"]:
                source = originals[item["block_id"]]
                self.assertEqual(page["content"][item["char_start"]:item["char_end"]], source["text"])
                self.assertEqual(item["char_end"] - item["char_start"], len(source["text"]))
                for field in ("bbox", "anchor_sha256", "raw_locator", "source_collection"):
                    self.assertEqual(item[field], source[field])
                self.assertEqual(item["source_type"], source["type"])
                mapped.append(item["block_id"])
        self.assertCountEqual(mapped, [ref for ref in originals if ref != "/figures/0"])
        self.assertEqual(projection["pages"][3]["content"], "")
        self.assertEqual(projection["pages"][3]["blocks"][0]["char_start"], 0)
        self.assertNotIn("SYNTHETIC_DISPLAY_LABEL", "".join(page["content"] for page in projection["pages"]))

    def test_dual_selected_text_keeps_native_and_alternate_provenance_in_context(self):
        block = next(b for b in self.bundle['blocks'] if b['block_id'] == '/body')
        block.update(text='1 μg/ml', native_text='1 mg/ml',
            native_raw_artifact={'artifact_path':'source_middle.json','sha256':'a'*64},
            transcription_selection={'native_text':'1 mg/ml','selected_text':'1 μg/ml',
                'ocr_refs':[{'artifact_path':'ocr/middle.json','raw_locator':'/pdf_info/0/preproc_blocks/2'}]})
        rows = self.source_rows(self.bundle)
        projection = build_pages(self.bundle, rows)
        context = select_page_context(projection, 1)
        page = context['pages'][0]
        span = next(b for b in page['blocks'] if b['block_id'] == '/body')
        self.assertEqual(page['content'][span['char_start']:span['char_end']], '1 μg/ml')
        self.assertEqual(span['native_text'], '1 mg/ml')
        self.assertEqual(span['transcription_selection'], block['transcription_selection'])
        self.assertEqual(span['native_raw_artifact'], block['native_raw_artifact'])
        span['transcription_selection']['selected_text'] = 'changed'
        self.assertEqual(block['transcription_selection']['selected_text'], '1 μg/ml')

    def test_cross_page_figure_has_one_owner_and_one_complete_image(self):
        projection = build_pages(self.bundle, self.rows)
        pages = projection["pages"]
        self.assertIn(self.figure_id, pages[1]["information_ids"])
        self.assertIn(self.figure_id, pages[2]["information_ids"])
        self.assertIn(self.figure_id, pages[1]["target_information_ids"])
        self.assertNotIn(self.figure_id, pages[2]["target_information_ids"])
        targets = [ref for page in pages for ref in page["target_information_ids"]]
        self.assertCountEqual(targets, [row["information_id"] for row in self.rows])
        self.assertEqual(len(targets), len(set(targets)))
        images = [item for page in pages for item in page["images"]]
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["information_id"], self.figure_id)
        self.assertEqual(images[0]["primary_block_id"], "/figures/0")
        self.assertEqual(images[0]["unit_type"], "figure")
        self.assertEqual(images[0]["artifact"]["sha256"], sha256(b"full.png").hexdigest())
        self.assertEqual(pages[2]["images"], [])

    def test_context_windows_clip_at_document_edges_and_do_not_reassign_targets(self):
        projection = build_pages(self.bundle, self.rows)
        for number, expected in ((1, [1, 2]), (2, [1, 2, 3]), (3, [2, 3, 4]), (4, [3, 4])):
            context = select_page_context(projection, number)
            self.assertEqual(context["schema_version"], "page-context-v1")
            self.assertEqual(context["page_number"], number)
            self.assertEqual([page["page_number"] for page in context["pages"]], expected)
            self.assertEqual(context["target_information_ids"], projection["pages"][number - 1]["target_information_ids"])
            visible = {ref for page in context["pages"] for ref in page["information_ids"]}
            self.assertEqual(set(context["context_information_ids"]), visible - set(context["target_information_ids"]))
        third = select_page_context(projection, 3)
        self.assertIn(self.figure_id, third["context_information_ids"])
        self.assertNotIn(self.figure_id, third["target_information_ids"])

    def test_partial_cross_page_information_is_reported_without_silent_truncation(self):
        projection = build_pages(self.bundle, self.rows)
        self.assertEqual(select_page_context(projection, 1)["missing_information_pages"], [3])
        self.assertEqual(select_page_context(projection, 2)["missing_information_pages"], [])
        self.assertEqual(select_page_context(projection, 4)["missing_information_pages"], [2])

    def test_target_spanning_beyond_adjacent_page_window_is_explicitly_incomplete(self):
        bundle = deepcopy(self.bundle)
        next(block for block in bundle["blocks"] if block["block_id"] == "/continuation")["page_index"] = 3
        projection = build_pages(bundle, self.source_rows(bundle))
        context = select_page_context(projection, 2)
        self.assertEqual(context["missing_information_pages"], [4])
        self.assertFalse(context["target_complete"])
        self.assertFalse(context["context_complete"])
        self.assertEqual(context["incomplete_information_refs"], [
            {"information_id": self.figure_id, "role": "target", "page_numbers": [4]}])
        self.assertTrue(select_page_context(projection, 3)["context_complete"])

    def test_projection_is_deterministic_and_detached_from_source_and_context(self):
        before_bundle, before_rows = deepcopy(self.bundle), deepcopy(self.rows)
        projection = build_pages(self.bundle, self.rows)
        self.assertEqual(projection, build_pages(deepcopy(self.bundle), deepcopy(self.rows)))
        self.assertEqual(self.bundle, before_bundle)
        self.assertEqual(self.rows, before_rows)
        self.assertEqual(len(projection["projection_sha256"]), 64)
        context = select_page_context(projection, 2)
        context["pages"][0]["blocks"][0]["bbox"][0] = 999
        context["pages"][1]["images"][0]["artifact"]["sha256"] = "f" * 64
        self.assertEqual(projection, build_pages(self.bundle, self.rows))
        projection["pages"][0]["blocks"][0]["bbox"][0] = 999
        self.assertEqual(self.bundle, before_bundle)
        self.assertEqual(self.rows, before_rows)

    def test_duplicate_mineru_indices_keep_stable_source_order_and_expose_ties(self):
        bundle = deepcopy(self.bundle)
        bundle["blocks"][0]["upstream_metadata"]["index"] = 1
        projection = build_pages(bundle, self.source_rows(bundle))
        first = projection["pages"][0]
        self.assertEqual([block["block_id"] for block in first["blocks"]], ["/body", "/header"])
        self.assertTrue(first["reading_order_ties"])

    def test_missing_nonfinite_boolean_and_text_reading_indices_fail_without_geometry_fallback(self):
        for invalid in (None, True, "1", float("inf"), float("nan")):
            bundle = deepcopy(self.bundle)
            bundle["blocks"][0]["upstream_metadata"]["index"] = invalid
            self.assert_error("reading_order_unavailable", lambda: build_pages(bundle, self.rows))
        bundle = deepcopy(self.bundle)
        bundle["blocks"][0]["upstream_metadata"].pop("index")
        self.assert_error("reading_order_unavailable", lambda: build_pages(bundle, self.rows))

    def test_missing_duplicate_cross_data_legacy_and_modified_information_are_rejected(self):
        invalid_rows = [self.rows[:-1], self.rows + [deepcopy(self.rows[0])]]
        for path, value in (("data_id", "c" * 64), ("information_id", ""), ("information_id", None),
                            ("semantic_type", "observation")):
            rows = deepcopy(self.rows)
            rows[0][path] = value
            invalid_rows.append(rows)
        for path, value in (("schema_version", "information-v1"), ("source_bundle_sha256", "f" * 64)):
            rows = deepcopy(self.rows)
            rows[0]["payload"][path] = value
            invalid_rows.append(rows)
        rows = deepcopy(self.rows)
        rows[0]["payload"]["source_blocks"][0]["text"] = "PRIVATE_TAMPERED_CONTENT"
        invalid_rows.append(rows)
        rows = deepcopy(self.rows)
        rows[1]["information_id"] = rows[0]["information_id"]
        invalid_rows.append(rows)
        for rows in invalid_rows:
            self.assert_error("invalid_page_projection", lambda: build_pages(self.bundle, rows))

    def test_context_rejects_nonphysical_or_out_of_range_page_numbers(self):
        projection = build_pages(self.bundle, self.rows)
        for number in (0, -1, 5, True, 1.0, "1", None):
            self.assert_error("invalid_page_number", lambda: select_page_context(projection, number))

    def test_context_rejects_a_modified_export_and_single_page_document_stays_single(self):
        projection = build_pages(self.bundle, self.rows)
        projection["pages"][0]["content"] = "PRIVATE_CHANGED_EXPORT"
        self.assert_error("invalid_page_projection", lambda: select_page_context(projection, 1))
        bundle = {**deepcopy(self.bundle), "pages": deepcopy(self.bundle["pages"][:1]),
                  "blocks": deepcopy(self.bundle["blocks"][:2]), "required_figures": []}
        context = select_page_context(build_pages(bundle, self.source_rows(bundle)), 1)
        self.assertEqual([page["page_number"] for page in context["pages"]], [1])
        self.assertEqual(context["context_information_ids"], [])
        self.assertEqual(context["missing_information_pages"], [])
        self.assertTrue(context["target_complete"])


if __name__ == "__main__":
    unittest.main()
