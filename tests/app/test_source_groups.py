"""Grouped source storage preserves original text, media and complete coverage."""

from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.information import fingerprints
from palimpsest.source_groups import build_source_groups, group_content_segments, verify_source_groups
from palimpsest.source_units import build_source_units, verify_source_units


def bundle():
    import test_source_units as fixtures
    factory = fixtures.SourceUnitsTests()
    source = {"schema_version": 1, "data_id": "b" * 64,
              "coordinate_system": "pdf_points_top_left",
              "pages": [{"page_index": p, "page_size": [612, 792]} for p in range(2)], "blocks": []}
    for ref, page, index, kind, text, image in (
            ("/header", 0, 0, "header", "PRIVATE_HEADER", False),
            ("/intro", 0, 1, "title", "Introduction", False),
            ("/intro-text", 0, 2, "text", "  Cafe\u0301 μ\r\n  ", False),
            ("/page", 0, 3, "page_number", "1", False),
            ("/intro-tail", 1, 0, "text", "Continued source paragraph.", False),
            ("/results", 1, 1, "title", "Results", False),
            ("/sub", 1, 2, "title", "First result", False),
            ("/image", 1, 3, "image", "", True),
            ("/table", 1, 4, "table", "<table>μ²</table>", True),
            ("/equation", 1, 5, "equation", "x²", True),
            ("/caption", 1, 6, "text", "A caption without a confirmed Figure inventory.", False),
            ("/footer", 1, 7, "footer", "PRIVATE_FOOTER", False)):
        block = factory.block(ref, kind, page, text, image=image)
        block["upstream_metadata"] = {"index": index}
        source["blocks"].append(block)
    return source


class SourceGroupsTests(unittest.TestCase):
    def test_cross_page_sections_furniture_media_and_exact_unicode_offsets(self):
        source = bundle()
        source["blocks"].reverse()  # Parser reading indices, not input-array order.
        before = deepcopy(source)
        groups = build_source_groups(source)
        self.assertEqual(source, before)
        self.assertEqual(groups, build_source_groups(source))
        self.assertEqual([p["title"] for p in groups],
                         ["Introduction", "First result", "Document page furniture"])
        self.assertEqual(groups[0]["content"], "Introduction\n\n  Cafe\u0301 μ\r\n  \n\nContinued source paragraph.")
        self.assertEqual(groups[-1]["block_ids"], ["/header", "/page", "/footer"])
        self.assertEqual(groups[1]["block_ids"], ["/results", "/sub", "/image", "/table", "/equation", "/caption"])
        self.assertTrue(all(p["kind"] == "text" and p["unit_type"] == "text" and
                            p["image_block_id"] is None and p["semantic_type"] is None for p in groups))
        by_id = {b["block_id"]: b for b in source["blocks"]}
        for group in groups:
            for segment in group_content_segments(source, group):
                ref = segment["source_block_id"]
                self.assertEqual(group["content"][segment["char_start"]:segment["char_end"]], by_id[ref]["text"])
                self.assertEqual(segment["source_char_range"], [0, len(by_id[ref]["text"])])
        ledger = verify_source_groups(source, groups)
        self.assertEqual(ledger["version"], "source-groups-v1")
        self.assertEqual(ledger["proposal_count"], 3)
        self.assertEqual(ledger["original_block_count"], 12)
        self.assertNotIn("PRIVATE_", json.dumps(ledger))
        self.assertEqual(Counter(ref for p in groups for ref in p["block_ids"]), Counter(by_id.keys()))
        old = fingerprints(source["data_id"], groups[1], by_id)
        by_id["/image"]["image_paths"][0]["sha256"] = "d" * 64
        self.assertNotEqual(old["identity_fingerprint"],
                            fingerprints(source["data_id"], groups[1], by_id)["identity_fingerprint"])

    def test_unclassified_single_empty_block_and_empty_document_are_preserved(self):
        source = bundle()
        source["blocks"] = [next(b for b in source["blocks"] if b["block_id"] == "/image")]
        group, = build_source_groups(source)
        self.assertEqual(group["title"], "Unclassified source content")
        self.assertEqual(group["content"], "")
        self.assertEqual(group["block_ids"], ["/image"])
        self.assertEqual(group_content_segments(source, group)[0]["char_end"], 0)
        self.assertEqual(verify_source_groups(source, [group])["original_block_count"], 1)
        source["blocks"] = []
        self.assertEqual(build_source_groups(source), [])
        self.assertEqual(verify_source_groups(source, [])["proposal_count"], 0)

    def test_required_figures_keep_exact_legacy_shape_and_caption_mapping(self):
        import test_source_units as fixtures
        fixture = fixtures.SourceUnitsTests()
        fixture.setUp()
        source = fixture.bundle
        for index, block in enumerate(source["blocks"]):
            block["upstream_metadata"] = {"index": index}
        groups = build_source_groups(source)
        figures = [p for p in groups if p["unit_type"] == "figure"]
        self.assertEqual(figures, [p for p in build_source_units(source) if p["unit_type"] == "figure"])
        self.assertEqual(len(figures), 6)
        by_id = {b["block_id"]: b for b in source["blocks"]}
        for group in figures:
            segments = group_content_segments(source, group)
            self.assertIsNone(segments[0]["source_char_range"])
            self.assertIsNone(segments[0]["char_start"])
            self.assertEqual(segments[0]["text_origin"], "derived_visual_reference")
            for segment in segments[1:]:
                if segment["char_start"] is not None:
                    self.assertEqual(group["content"][segment["char_start"]:segment["char_end"]],
                                     by_id[segment["source_block_id"]]["text"])
                else:
                    self.assertEqual(segment["text_origin"], "source_block_only")
        self.assertEqual(verify_source_groups(source, groups)["original_block_count"], 35)
        for ref in source["required_figures"][0]["caption_block_ids"]:
            by_id[ref]["text"] = ""
        figure = next(p for p in build_source_groups(source) if p["image_block_id"] == "/figures/0")
        self.assertEqual(figure["content"], "")
        self.assertEqual([s["char_end"] for s in group_content_segments(source, figure)[3:]], [0, 0])

    def test_changed_content_membership_order_and_extra_fields_are_rejected(self):
        source = bundle()
        for mutation in ("content", "missing", "duplicate", "order", "field"):
            groups = build_source_groups(source)
            if mutation == "content":
                groups[0]["content"] = groups[0]["content"].strip()
                groups[0]["content"] += "invented"
            elif mutation == "missing":
                groups[0]["block_ids"].pop()
            elif mutation == "duplicate":
                groups.append(deepcopy(groups[0]))
            elif mutation == "order":
                groups.reverse()
            else:
                groups[0]["authority"] = "accepted"
            with self.subTest(mutation=mutation), self.assertRaises(PalimpsestError) as failure:
                verify_source_groups(source, groups)
            self.assertEqual(failure.exception.code, "source_group_mismatch")
        group = build_source_groups(source)[0]
        group["content"] += "invented"
        with self.assertRaises(PalimpsestError):
            group_content_segments(source, group)

    def test_missing_reading_order_unsupported_or_duplicate_source_never_pass(self):
        for mutation in ("index", "unsupported", "duplicate"):
            source = bundle()
            if mutation == "index":
                source["blocks"][0]["upstream_metadata"].pop("index")
            elif mutation == "unsupported":
                source["blocks"][0]["supported"] = False
            else:
                source["blocks"].append(deepcopy(source["blocks"][0]))
            with self.subTest(mutation=mutation), self.assertRaises(PalimpsestError):
                build_source_groups(source)

    def test_existing_transcription_review_is_retained_and_ledger_is_independent(self):
        source = bundle()
        source["transcription_selection"] = {"status": "review_required", "version": "selection-v1",
            "unresolved": [{"block_id": "/intro-text"}], "unmatched_ocr_block_ids": ["/unmatched"],
            "blocks": [{"changes": [{"start": 1}]}]}
        proposals = build_source_groups(source)
        ledger = verify_source_groups(source, proposals)
        legacy = verify_source_units(source, build_source_units(source))
        self.assertEqual(ledger["transcription_review"], legacy["transcription_review"])
        self.assertFalse(ledger["transcription_review"]["source_fidelity_verified"])
        ledger["unit_manifest"][0]["block_ids"].clear()
        self.assertTrue(proposals[0]["block_ids"])

    def test_shared_boundary_helper_keeps_historical_projection_hashes(self):
        import test_section_projection as fixtures
        from palimpsest.section_projection import build_sections, document_context
        source = fixtures.evidence()
        view = build_sections(source)
        self.assertEqual(view["projection_sha256"], "33a2a2f090949b6b4a0f08b446376495383520724a37ee27c76f1788dc413089")
        self.assertEqual(document_context(source, expected_projection_sha256=view["projection_sha256"])["context_sha256"],
                         "153e0f406e0923582cc7730827829542f5167a61a994f9fe4c16a9fc7dc8edba")

    def test_grouped_conversion_has_no_provider_database_or_parser_dependency(self):
        script = '''
import importlib.abc, sys
class BlockAdapters(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('palimpsest.codex_provider', 'palimpsest.legacy_semantic_d2i',
                        'palimpsest.mineru_adapter', 'psycopg'):
            raise AssertionError('Grouped conversion imported an inference or persistence adapter')
sys.meta_path.insert(0, BlockAdapters())
from palimpsest.source_groups import build_source_groups, verify_source_groups
bundle = {'schema_version':1,'data_id':'b'*64,'coordinate_system':'pdf_points_top_left',
          'pages':[{'page_index':0,'page_size':[612,792]}],'blocks':[]}
assert verify_source_groups(bundle, build_source_groups(bundle))['status'] == 'complete'
'''
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
        result = subprocess.run([sys.executable, "-B", "-c", script], env=environment,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
