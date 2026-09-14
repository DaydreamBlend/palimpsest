"""Python syntax grouping and exact retained dossier/member source provenance."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from palimpsest import code_snapshot
from palimpsest.code_adapter import (CODE_ALGORITHM, CODE_PARSER, CODE_SCHEMA,
    build_code_units, code_content_segments, parse_code_snapshot, verify_code_units)
from palimpsest.errors import PalimpsestError
from palimpsest.information import fingerprints


class CodeAdapterTests(unittest.TestCase):
    def dossier(self, members):
        with TemporaryDirectory(prefix="code-adapter-") as directory:
            root = Path(directory)
            for name, content in members.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
            code_snapshot.snapshot(root, root / "snapshot", list(members))
            return (root / "snapshot/dossier.md").read_bytes()

    def parse(self, members):
        raw = self.dossier(members)
        return raw, parse_code_snapshot(raw, data_id=sha256(raw).hexdigest())

    def member_blocks(self, bundle, name="example.py"):
        return [block for block in bundle["blocks"] if block["code_context"].get("member_path") == name]

    def assert_preserved(self, raw, bundle):
        proposals = build_code_units(bundle)
        self.assertEqual(b"".join(p["content"].encode("utf-8") for p in proposals), raw)
        self.assertEqual(bundle["schema_version"], CODE_SCHEMA)
        self.assertEqual(bundle["source_byte_size"], len(raw))
        self.assertEqual(bundle["source_character_count"], len(raw.decode("utf-8")))
        cursor = byte_cursor = 0
        by_id = {block["block_id"]: block for block in bundle["blocks"]}
        for block, proposal in zip(bundle["blocks"], proposals):
            location = block["text_range"]
            self.assertEqual((location["char_start"], location["byte_start"]), (cursor, byte_cursor))
            cursor, byte_cursor = location["char_end"], location["byte_end"]
            self.assertEqual(raw[location["byte_start"]:byte_cursor], proposal["content"].encode("utf-8"))
            self.assertEqual(block["anchor_sha256"], sha256(proposal["content"].encode("utf-8")).hexdigest())
            self.assertIsNone(proposal["semantic_type"])
            self.assertEqual(proposal["kind"], "text")
            self.assertIsNone(block["page_index"])
            self.assertIsNone(block["bbox"])
            fingerprints(bundle["data_id"], proposal, by_id)
            segment, = code_content_segments(bundle, proposal)
            self.assertEqual(segment["source_text_range"], location)
            self.assertEqual(segment["code_context"], block["code_context"])
        self.assertEqual((cursor, byte_cursor), (len(raw.decode("utf-8")), len(raw)))
        for entry in bundle["snapshot_manifest"]["files"]:
            members = self.member_blocks(bundle, entry["path"])
            reconstructed = "".join(block["text"] for block in members).encode("utf-8")
            self.assertEqual(reconstructed, raw[entry["body_byte_start"]:entry["body_byte_end"]])
            self.assertEqual(sha256(reconstructed).hexdigest(), entry["sha256"])
            cursor = byte_cursor = 0
            for block in members:
                context = block["code_context"]
                self.assertEqual(context["member_sha256"], entry["sha256"])
                location = context["member_text_range"]
                self.assertEqual((location["char_start"], location["byte_start"]), (cursor, byte_cursor))
                cursor, byte_cursor = location["char_end"], location["byte_end"]
        ledger = verify_code_units(bundle, proposals)
        self.assertEqual(ledger["version"], CODE_ALGORITHM)
        self.assertEqual(ledger["provided_block_ids"], ledger["covered_block_ids"])
        self.assertEqual(len(ledger["unit_manifest"]), len(proposals))
        self.assertEqual(ledger["grouping_policy"]["semantic_llm_calls"], 0)
        return proposals

    def test_unicode_bom_mixed_newlines_decorators_async_and_all_gaps(self):
        source = ('\ufeff"""문서 μ 😀 Cafe\u0301"""\r\nimport os\r\nCONFIG = "원문"\r\n\r\n'
            '# first function comment\r\n@decorate("μ")\r\nasync def 첫째(x="😀"):\r\n'
            '    """Exact docstring."""\r\n    return x\r\n\r\n# gap\r\n'
            'def second():\r    return 2\n\n# final comment without newline')
        raw, bundle = self.parse({"example.py": source})
        self.assert_preserved(raw, bundle)
        blocks = self.member_blocks(bundle)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["code_context"]["group_kind"], "module_preamble")
        self.assertTrue(blocks[1]["text"].startswith('@decorate("μ")\r\n'))
        first, second = blocks[1]["code_context"]["symbols"]
        self.assertEqual((first["name"], first["kind"]), ("첫째", "async_function"))
        self.assertEqual(first["member_text_range"]["line_start"], 6)
        self.assertEqual(first["member_text_range"]["line_end"], 9)
        self.assertEqual(second["member_text_range"]["line_start"], 12)
        for symbol in (first, second):
            local, global_ = symbol["member_text_range"], symbol["text_range"]
            exact = source[local["char_start"]:local["char_end"]]
            self.assertEqual(exact.encode("utf-8"), raw[global_["byte_start"]:global_["byte_end"]])
        self.assertEqual(bundle["profile"], CODE_PARSER)
        self.assertEqual(bundle, parse_code_snapshot(raw, data_id=bundle["data_id"]))

    def test_first_line_bom_exact_symbol_offsets(self):
        for source in ('\ufeffdef 함수(): return "😀"', '\ufeff@decorator\r\ndef 함수(): return "μ"'):
            raw, bundle = self.parse({"example.py": source})
            self.assert_preserved(raw, bundle)
            symbol, = self.member_blocks(bundle)[0]["code_context"]["symbols"]
            location = symbol["member_text_range"]
            self.assertEqual(location["char_start"], 1)
            self.assertEqual(location["byte_start"], 3)
            self.assertEqual(source[location["char_start"]:location["char_end"]], source[1:])

    def test_fake_definitions_inside_strings_and_nested_definitions_do_not_split(self):
        source = ('TEXT = """\ndef fake():\nclass Forged:\n"""\n'
            'def outer():\n    def inner():\n        return "def fake_again():"\n    return inner\n'
            'class Container:\n    class Nested:\n        async def method(self):\n            return 1\n')
        raw, bundle = self.parse({"example.py": source})
        self.assert_preserved(raw, bundle)
        blocks = self.member_blocks(bundle)
        self.assertEqual(len(blocks), 2)
        symbols = blocks[1]["code_context"]["symbols"]
        self.assertEqual([s["qualified_name"] for s in symbols],
            ["outer", "outer.inner", "Container", "Container.Nested", "Container.Nested.method"])
        self.assertNotIn("fake", [s["name"] for s in symbols])

    def test_large_classes_split_at_members_with_exact_enclosing_context(self):
        padding = "x" * 3400
        source = ('class Large:\n    """class documentation"""\n    SETTING = 3\n'
            f'    @decorator\n    def first(self):\n        return "{padding}"\n\n'
            '    # method gap retained\n'
            f'    async def second(self):\n        return "{padding}"\n'
            '    class Nested:\n        """nested context"""\n'
            f'        def third(self):\n            return "{padding}"\n'
            f'        def fourth(self):\n            return "{padding}"\n')
        raw, bundle = self.parse({"example.py": source})
        self.assert_preserved(raw, bundle)
        blocks = self.member_blocks(bundle)
        self.assertEqual([b["code_context"]["group_kind"] for b in blocks],
            ["class_preamble", "definitions", "definitions", "class_preamble", "definitions", "definitions"])
        self.assertIn('SETTING = 3', blocks[0]["text"])
        self.assertTrue(blocks[1]["text"].startswith('    @decorator\n'))
        self.assertIn('# method gap retained', blocks[1]["text"])
        self.assertEqual([s["qualified_name"] for s in blocks[-1]["code_context"]["enclosing_symbols"]],
            ["Large", "Large.Nested"])
        self.assertEqual(blocks[-1]["code_context"]["symbols"][0]["qualified_name"], "Large.Nested.fourth")

    def test_target_is_soft_and_small_siblings_group_without_splitting_function(self):
        target = CODE_PARSER["target_characters"]
        source = 'def large():\n    return "' + ('x' * (target + 100)) + '"\n'
        source += '\ndef small(): return 1\n\ndef another(): return 2\n'
        raw, bundle = self.parse({"example.py": source})
        self.assert_preserved(raw, bundle)
        blocks = self.member_blocks(bundle)
        self.assertEqual(len(blocks), 2)
        self.assertGreater(len(blocks[0]["text"]), target)
        self.assertEqual([s["name"] for s in blocks[1]["code_context"]["symbols"]], ["small", "another"])

    def test_empty_bom_whitespace_and_non_python_members_remain_addressable(self):
        members = {"empty.py": "", "bom.py": "\ufeff", "space.py": "\r\n  \n# comment",
            "config.toml": 'value = "μ"\r\n', 'docs/한글 spaced.md': '# Metadata\n',
            "empty.txt": "", "types.pyi": 'def declared() -> int: ...\n'}
        raw, bundle = self.parse(members)
        self.assert_preserved(raw, bundle)
        for name in members:
            block, = self.member_blocks(bundle, name)
            self.assertEqual(block["text"], members[name])
            context = block["code_context"]
            self.assertEqual(context["parse_status"], "parsed" if name.endswith((".py", ".pyi")) else "not_python")
            if not members[name]:
                self.assertEqual(context["member_text_range"], {"byte_start": 0, "byte_end": 0,
                    "char_start": 0, "char_end": 0, "line_start": 1, "line_end": 1})
        metadata = [b for b in bundle["blocks"] if b["code_context"]["representation_role"] == "dossier_metadata"]
        self.assertTrue(metadata[0]["text"].startswith('# Codebase source snapshot'))
        self.assertIn('## Snapshot manifest', metadata[-1]["text"])

    def test_syntax_errors_remain_whole_files_with_reported_error(self):
        source = 'def valid(): return 1\n\ndef broken(:\n    pass\n# trailing source\n'
        raw, bundle = self.parse({"example.py": source})
        self.assert_preserved(raw, bundle)
        block, = self.member_blocks(bundle)
        self.assertEqual(block["text"], source)
        context = block["code_context"]
        self.assertEqual(context["parse_status"], "syntax_error")
        self.assertEqual(context["parse_error"]["line"], 3)
        self.assertEqual(context["symbols"], [])

    def test_parenthesized_multiline_decorators_include_actual_at_lines(self):
        source = ('# preamble\r\n@(\r\n    decorate\r\n)\r\n@other(\r\n    "@ not syntax"\r\n)\r\n'
            'def decorated():\r\n    return 1\r\n')
        raw, bundle = self.parse({"example.py": source})
        self.assert_preserved(raw, bundle)
        preamble, function = self.member_blocks(bundle)
        self.assertEqual(preamble["text"], '# preamble\r\n')
        self.assertTrue(function["text"].startswith('@(\r\n'))
        symbol, = function["code_context"]["symbols"]
        location = symbol["member_text_range"]
        self.assertEqual(location["line_start"], 2)
        self.assertEqual(source[location["char_start"]:location["char_end"]], source[len(preamble["text"]):-2])

    def test_parsing_never_executes_imports_source_files_or_network(self):
        raw = self.dossier({"example.py": 'import missing_module\nraise RuntimeError("never execute")\n'})
        with patch("builtins.open", side_effect=AssertionError("No filesystem access")), \
                patch("urllib.request.urlopen", side_effect=AssertionError("No network access")):
            bundle = parse_code_snapshot(raw, data_id=sha256(raw).hexdigest())
            self.assert_preserved(raw, bundle)

    def test_dossier_hash_member_hash_manifest_and_escaped_paths_are_verified(self):
        raw = self.dossier({"example.py": 'def original(): return 1\n'})
        with self.assertRaises(PalimpsestError) as error:
            parse_code_snapshot(raw, data_id="a" * 64)
        self.assertEqual(error.exception.code, "integrity_conflict")
        for altered in (raw.replace(b"original", b"modified", 1), b"def direct_code(): pass\n", b"\xff", b"x\x00y"):
            with self.subTest(altered=altered[:20]), self.assertRaises(PalimpsestError):
                parse_code_snapshot(altered, data_id=sha256(altered).hexdigest())
        marker = raw.rfind(code_snapshot.FOOTER)
        embedded = json.loads(raw[marker + len(code_snapshot.FOOTER):-len(code_snapshot.ENDING)])
        for path in ("../outside.py", "/absolute.py", "C:/outside.py", "src\\escape.py", "src/../escape.py"):
            altered = deepcopy(embedded)
            altered["files"][0]["path"] = path
            invalid = raw[:marker + len(code_snapshot.FOOTER)] + code_snapshot._json(altered) + code_snapshot.ENDING
            with self.subTest(path=path), self.assertRaises(PalimpsestError):
                parse_code_snapshot(invalid, data_id=sha256(invalid).hexdigest())

    def test_tampered_source_structure_profile_member_metadata_and_units_are_rejected(self):
        _, original = self.parse({"example.py": 'CONFIG = 1\ndef first(): return "μ"\n'})
        for field in ("text", "anchor", "offset", "bool", "member", "symbol", "profile", "count", "order"):
            bundle = deepcopy(original)
            block = self.member_blocks(bundle)[1]
            if field == "text":
                block["text"] += "changed"
            elif field == "anchor":
                block["anchor_sha256"] = "c" * 64
            elif field == "offset":
                block["text_range"]["byte_end"] -= 1
            elif field == "bool":
                bundle["blocks"][0]["text_range"]["char_start"] = False
            elif field == "member":
                block["code_context"]["member_sha256"] = "c" * 64
            elif field == "symbol":
                block["code_context"]["symbols"][0]["name"] = "invented"
            elif field == "profile":
                bundle["profile"]["version"] = "wrong"
            elif field == "count":
                bundle["source_line_count"] += 1
            else:
                bundle["blocks"].reverse()
            with self.subTest(field=field), self.assertRaises(PalimpsestError):
                build_code_units(bundle)
        for field in ("content", "title", "drop", "duplicate", "order", "extra"):
            proposals = build_code_units(original)
            if field in ("content", "title"):
                proposals[0][field] += " changed"
            elif field == "drop":
                proposals.pop()
            elif field == "duplicate":
                proposals.append(deepcopy(proposals[0]))
            elif field == "order":
                proposals.reverse()
            else:
                proposals[0]["accepted"] = True
            with self.subTest(field=field), self.assertRaises(PalimpsestError) as error:
                verify_code_units(original, proposals)
            self.assertEqual(error.exception.code, "source_group_mismatch")

    def test_same_source_member_in_other_data_has_distinct_information_identity(self):
        _, first = self.parse({"example.py": 'def first(): return 1\n'})
        _, second = self.parse({"example.py": 'def first(): return 1\n', "z.txt": "Extra source\n"})
        first_block, = self.member_blocks(first)
        second_block, = self.member_blocks(second)
        self.assertEqual(first_block["text"], second_block["text"])
        values = []
        for bundle, block in ((first, first_block), (second, second_block)):
            proposals = build_code_units(bundle)
            proposal = next(p for p in proposals if p["block_ids"] == [block["block_id"]])
            values.append(fingerprints(bundle["data_id"], proposal, {b["block_id"]: b for b in bundle["blocks"]}))
        self.assertNotEqual(values[0]["identity_fingerprint"], values[1]["identity_fingerprint"])


if __name__ == "__main__":
    unittest.main()
