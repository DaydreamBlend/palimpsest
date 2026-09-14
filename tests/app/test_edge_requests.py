"""N2E request type constraints; no database, model, or semantic filtering."""

from copy import deepcopy
import json
import unittest

from palimpsest.knowledge_requests import edge_generation_request
from palimpsest.n2e import EDGE_SCHEMA, normalize_edges


def snapshot(kinds=('observation', 'proposition', 'proposition')):
    return {'existing_edges': [], 'input': {'schema_version': 'n2e-input-v1', 'nodes': [
        {'statement': 'The same metadata wording does not determine the node kind.',
         'kind': kind, 'knode_revision_id': f'019a5c1b-7f00-7000-8000-{number:012x}',
         'knode_id': f'019a5c1b-7f00-7000-8001-{number:012x}'}
        for number, kind in enumerate(kinds, 1)]}}


class EdgeRequestTests(unittest.TestCase):
    def test_sources_keep_both_kinds_but_targets_only_include_actual_propositions(self):
        value = snapshot()
        before = deepcopy(value)
        prompt, schema = edge_generation_request(value)
        nodes = value['input']['nodes']
        fields = schema['properties']['edges']['items']['properties']
        self.assertEqual(fields['from_revision_id']['enum'], [node['knode_revision_id'] for node in nodes])
        self.assertEqual(fields['to_revision_id']['enum'], [node['knode_revision_id'] for node in nodes[1:]])
        self.assertIn('target must have kind=proposition', prompt)
        self.assertEqual(value, before)
        self.assertEqual(EDGE_SCHEMA(fields['from_revision_id']['enum'])['properties']['edges']['items']
                         ['properties']['to_revision_id']['enum'], fields['from_revision_id']['enum'])

    def test_no_proposition_allows_only_empty_edges_without_empty_enums(self):
        def check_enums(value):
            if isinstance(value, dict):
                if 'enum' in value:
                    self.assertTrue(value['enum'])
                for child in value.values():
                    check_enums(child)
            elif isinstance(value, list):
                for child in value:
                    check_enums(child)
        for kinds in (('observation',), ('observation', 'observation'), ()):
            with self.subTest(kinds=kinds):
                value = snapshot(kinds)
                prompt, schema = edge_generation_request(value)
                self.assertEqual(schema['properties']['edges']['maxItems'], 0)
                check_enums(schema)
                self.assertIn('return edges=[] and complete=true', prompt)
                self.assertEqual(normalize_edges({'edges': [], 'complete': True},
                    {node['knode_revision_id']: node for node in value['input']['nodes']}), [])

    def test_recursive_object_order_is_irrelevant_but_reference_array_order_is_preserved(self):
        value = snapshot()
        ordered_objects = json.loads(json.dumps(value, sort_keys=True))
        self.assertNotEqual(list(value['input']['nodes'][0]), list(ordered_objects['input']['nodes'][0]))
        original = edge_generation_request(value)
        self.assertEqual(original, edge_generation_request(ordered_objects))
        reordered_array = deepcopy(value)
        reordered_array['input']['nodes'].reverse()
        changed = edge_generation_request(reordered_array)
        self.assertNotEqual(original, changed)
        self.assertEqual(changed[1]['properties']['edges']['items']['properties']['from_revision_id']['enum'],
                         [node['knode_revision_id'] for node in reordered_array['input']['nodes']])


if __name__ == '__main__':
    unittest.main()
