"""Effective relation projections with scripted SQL reads; no DB or model calls."""

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from palimpsest.edge_projection import resolve, derive_contested
from palimpsest.errors import PalimpsestError


def uid(value):
    return f'019947e2-1234-7000-8000-{value:012x}'


def fixture(predicate='contradicts'):
    nodes = [{'knode_id': uid(value), 'knode_revision_id': uid(value + 10),
        'current_revision_id': uid(value + 10), 'kind': 'proposition',
        'current_applicability': 'current_premises', 'current_support_signature': str(value) * 64,
        'statement': f'Private source claim {value}', 'semantic_payload': {'value': value}}
        for value in (1, 2)]
    edge = {'kedge_id': uid(30), 'kedge_revision_id': uid(31), 'current_revision_id': uid(31),
        'from_knode_id': uid(1), 'to_knode_id': uid(2),
        'from_knode_revision_id': uid(11), 'to_knode_revision_id': uid(12),
        'origin_record_id': uid(32), 'predicate': predicate, 'content_fingerprint': 'a' * 64}
    return nodes, [edge]


def event(order, applicable, source=11, target=12, semantic=31):
    return {'applicability_event_id': uid(100 + order), 'event_order': order,
        'kedge_id': uid(30), 'semantic_kedge_revision_id': uid(semantic),
        'from_knode_revision_id': uid(source), 'to_knode_revision_id': uid(target), 'applicable': applicable}


class Reads:
    def __init__(self, *, modern=True, status='applicable', events=(), fences=(), version=42, modern_schema=None):
        self.modern, self.status, self.events, self.fences, self.version = modern, status, events, fences, version
        self.calls = []
        self.modern_schema = modern if modern_schema is None else modern_schema

    def execute(self, query, values=None):
        self.calls.append((query, values))
        if not query.lstrip().startswith('SELECT'):
            raise AssertionError('Projection must not write or open migrations')
        if 'to_regprocedure' in query:
            result = {'name': 'canonical_store.current_knowledge_edge_applicability(uuid)' if self.modern else None,
                      'modern_schema': self.modern_schema}
        elif 'FROM compiler_runtime.knowledge_state' in query:
            result = {'version': self.version}
        elif 'FROM canonical_store.knowledge_edge_applicability_events' in query:
            result = list(self.events)
        elif 'FROM compiler_runtime.n2e_review_targets' in query:
            result = list(self.fences)
        elif 'SELECT canonical_store.current_knowledge_edge_applicability' in query:
            result = {'status': self.status}
        else:
            raise AssertionError('Unexpected projection SQL: ' + query)
        return SimpleNamespace(fetchone=lambda: deepcopy(result), fetchall=lambda: deepcopy(result))


class EdgeProjectionTests(unittest.TestCase):
    def test_active_contradiction_marks_both_sides_without_mutating_or_leaking_opponent(self):
        nodes, edges = fixture()
        before = deepcopy((nodes, edges))
        projected = resolve(Reads(), nodes, edges)
        annotated = derive_contested(nodes, projected)
        self.assertTrue(projected[0]['usable'])
        self.assertEqual(projected[0]['effective_edge_ref']['applicability_basis_ref'], uid(32))
        self.assertEqual([node['epistemic_projection'] for node in annotated], ['contested', 'contested'])
        self.assertEqual(set(annotated[0]) - set(nodes[0]), {'epistemic_projection'})
        self.assertNotIn(nodes[1]['statement'], json.dumps(annotated[0]))
        self.assertNotIn(nodes[1]['knode_id'], json.dumps(annotated[0]))
        self.assertEqual((nodes, edges), before)

    def test_legacy_latest_negative_beats_original_and_other_pairs_are_ignored(self):
        nodes, edges = fixture('supports')
        events = [event(1, True), event(2, False), event(3, True, source=99), event(4, True, semantic=99)]
        conn = Reads(modern=False, events=events)
        edge = resolve(conn, nodes, edges)[0]
        self.assertEqual(edge['applicability_status'], 'inapplicable')
        self.assertEqual(edge['applicability'], 'not_applicable')
        self.assertIs(edge['applicable'], False)
        self.assertFalse(edge['usable'])
        self.assertIsNone(edge['effective_edge_ref'])
        self.assertEqual(edge['applicability_basis_ref'], uid(102))
        self.assertFalse(any('n2e_review_targets' in query for query, _ in conn.calls))
        self.assertEqual(derive_contested(nodes, [edge])[0]['epistemic_projection'], 'uncontested')

    def test_unreviewed_changed_pair_is_pending_and_does_not_rewrite_original(self):
        nodes, edges = fixture()
        nodes[0]['knode_revision_id'] = nodes[0]['current_revision_id'] = uid(13)
        edge = resolve(Reads(modern=False), nodes, edges)[0]
        self.assertEqual(edge['applicability_status'], 'pending')
        self.assertIsNone(edge['applicable'])
        self.assertIsNone(edge['effective_edge_ref'])
        self.assertEqual(edge['from_knode_revision_id'], uid(11))
        self.assertEqual(edge['effective_from_revision_id'], uid(13))
        self.assertFalse(edge['usable'])

    def test_exact_pending_fence_masks_prior_positive_even_after_failed_review(self):
        nodes, edges = fixture()
        fence = {'execution_id': uid(60), 'semantic_kedge_revision_id': uid(31),
            'from_knode_revision_id': uid(11), 'to_knode_revision_id': uid(12), 'fence_order': 5}
        active = resolve(Reads(events=[event(4, True)]), nodes, edges)[0]
        pending = resolve(Reads(events=[event(4, True)], fences=[fence]), nodes, edges)[0]
        self.assertEqual(pending['applicability_status'], 'pending')
        self.assertIsNone(pending['applicable'])
        self.assertTrue(pending['pending_revalidation'])
        self.assertFalse(pending['usable'])
        self.assertIsNone(pending['effective_edge_ref'])
        self.assertNotEqual(active['projection_key'], pending['projection_key'])
        self.assertEqual(derive_contested(nodes, [pending])[0]['epistemic_projection'], 'uncontested')
        renewed = resolve(Reads(events=[event(6, True)], fences=[fence], version=43), nodes, edges)[0]
        self.assertTrue(renewed['usable'])
        self.assertFalse(renewed['pending_revalidation'])
        self.assertEqual(renewed['effective_edge_ref']['applicability_basis_ref'], uid(106))

    def test_stale_or_missing_endpoint_is_unusable_despite_original_positive(self):
        for modern in (True, False):
            nodes, edges = fixture()
            nodes[0]['current_applicability'] = 'needs_revalidation'
            result = resolve(Reads(modern=modern), nodes, edges)
            self.assertEqual(result[0]['applicability_status'], 'endpoint_unusable')
            self.assertFalse(result[0]['usable'])
            self.assertEqual(derive_contested(nodes, result)[1]['epistemic_projection'], 'uncontested')
            result = resolve(Reads(modern=modern), nodes[:1], edges)
            self.assertFalse(result[0]['usable'])
            self.assertIsNone(result[0]['effective_edge_ref'])

    def test_sql_support_fence_and_historical_result_are_respected(self):
        nodes, edges = fixture()
        for status in ('pending', 'inapplicable', 'endpoint_unusable', 'historical'):
            result = resolve(Reads(status=status), nodes, edges)
            self.assertEqual(result[0]['applicability_status'], status)
            self.assertFalse(result[0]['usable'])
            self.assertTrue(all(node['epistemic_projection'] == 'uncontested' for node in derive_contested(nodes, result)))

    def test_other_predicates_never_create_contested_and_current_support_changes_key(self):
        for predicate in ('supports', 'qualifies', 'composes', 'supersedes'):
            nodes, edges = fixture(predicate)
            first = resolve(Reads(), nodes, edges)
            self.assertEqual([node['epistemic_projection'] for node in derive_contested(nodes, first)],
                             ['uncontested', 'uncontested'])
            nodes[0]['current_support_signature'] = 'f' * 64
            second = resolve(Reads(), nodes, edges)
            self.assertNotEqual(first[0]['projection_key'], second[0]['projection_key'])

    def test_unsupported_modern_status_does_not_silently_fall_back(self):
        nodes, edges = fixture()
        with self.assertRaises(PalimpsestError) as raised:
            resolve(Reads(status='unknown-new-status'), nodes, edges)
        self.assertEqual(raised.exception.code, 'edge_projection_status_invalid')
        with self.assertRaises(PalimpsestError) as raised:
            resolve(Reads(modern=False, modern_schema=True), nodes, edges)
        self.assertEqual(raised.exception.code, 'edge_projection_schema_incomplete')


if __name__ == '__main__':
    unittest.main()
