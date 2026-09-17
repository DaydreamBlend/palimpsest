import unittest

from palimpsest import wisdom_groups


def catalog():
    return {"schema_version": wisdom_groups.SCHEMA, "nodes": [
        {"knode_revision_id": "a", "statement": "A"},
        {"knode_revision_id": "b", "statement": "B"},
        {"knode_revision_id": "c", "statement": "C"},
    ], "bge_neighbors": [], "effective_edges": [], "source_contexts": []}


class WisdomGroupTests(unittest.TestCase):
    def test_plan_requires_exact_single_assignment(self):
        value = {"schema_version": wisdom_groups.SCHEMA, "status": "complete",
                 "groups": [{"group_key": "g1", "title": "첫 묶음",
                             "rationale": "관련 항목"},
                            {"group_key": "g2", "title": "둘째 묶음",
                             "rationale": "별도 항목"}],
                 "assignments": {"a": "g1", "b": "g1", "c": "g2"}}
        plan = wisdom_groups.normalize_plan(value, catalog())
        self.assertEqual(["g1", "g2"], [group["group_key"] for group in plan["groups"]])
        prompt, schema = wisdom_groups.validation_request(catalog(), plan)
        self.assertIn("VALIDATION_JSON", prompt)
        self.assertEqual({"g1", "g2"}, set(schema["properties"]["group_checks"]["items"]["enum"]))
        value["assignments"]["c"] = "missing"
        with self.assertRaisesRegex(ValueError, "invalid_k2w_group_plan"):
            wisdom_groups.normalize_plan(value, catalog())

    def test_accepted_validation_requires_every_positive_check(self):
        plan = wisdom_groups.normalize_plan({"schema_version": wisdom_groups.SCHEMA,
            "status": "complete", "groups": [{"group_key": "g", "title": "묶음",
                "rationale": "관련 항목"}], "assignments": {"a": "g", "b": "g", "c": "g"}}, catalog())
        value = {"verdict": "accepted", "checks": {
            "all_k_covered_once": True, "allowed_ids_only": True,
            "not_overfragmented": True, "not_overbroad": True, "signals_are_hints_only": True},
            "group_checks": [], "summary": "모든 묶음이 적절함", "reason_codes": []}
        self.assertTrue(wisdom_groups.accept_validation(value, plan)["accepted"])
        value["checks"]["not_overbroad"] = False
        with self.assertRaisesRegex(ValueError, "inconsistent_k2w_group_validation"):
            wisdom_groups.accept_validation(value, plan)

    def test_validation_batches_are_compact_and_cover_every_group(self):
        full = catalog()
        full["nodes"][0]["semantic_payload"] = {"large": "unused"}
        plan = wisdom_groups.normalize_plan({"schema_version": wisdom_groups.SCHEMA,
            "status": "complete", "groups": [
                {"group_key": "g1", "title": "첫 주제", "rationale": "첫 근거"},
                {"group_key": "g2", "title": "둘째 주제", "rationale": "둘째 근거"}],
            "assignments": {"a": "g1", "b": "g1", "c": "g2"}}, full)
        batches = wisdom_groups.validation_batches(full, plan, batch_size=1)
        self.assertEqual([["g1"], ["g2"]],
            [[group["group_key"] for group in item["plan"]["groups"]] for item in batches])
        self.assertEqual({"a", "b", "c"}, {node["knode_revision_id"]
            for item in batches for node in item["catalog"]["nodes"]})
        self.assertTrue(all("semantic_payload" not in node
            for item in batches for node in item["catalog"]["nodes"]))
        self.assertTrue(all("all_group_overview" in item["prompt"] for item in batches))


if __name__ == "__main__":
    unittest.main()
