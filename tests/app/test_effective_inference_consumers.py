"""Exact Edge-derived inference consumers; synthetic evidence, no DB/provider."""

from copy import deepcopy
from hashlib import sha256
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from palimpsest import knowledge_provenance as provenance, wiki_query, desktop_read
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.wiki_retrieval import knowledge_projection
from test_wiki_query_inference import inference_context, inferred_proposal, decision, uid
from test_wiki_inference_retrieval import fixture as retrieval_fixture
import test_wiki_query_runtime as runtime_fixture


def edge_premise(first=None, second=None):
    first, second = first or uid(101), second or uid(102)
    return {'ordinal': 0, 'execution_id': uid(500), 'input_ordinal': 0,
        'kedge_id': uid(501), 'predicate': 'supports', 'qualifiers': {'scope': 'synthetic', 'conditions': []},
        'original_from_revision_id': first, 'original_to_revision_id': second,
        'effective_edge_ref': {'semantic_kedge_revision_id': uid(502),
            'from_knode_revision_id': first, 'to_knode_revision_id': second,
            'applicability_basis_type': 'applicability_event', 'applicability_basis_ref': uid(503),
            'relation_read_state_token': 'a' * 64}, 'endpoint_support_signatures': ['b' * 64, 'c' * 64]}


def mixed_context():
    context = inference_context()
    context['knowledge_inference_profile'] = provenance.EFFECTIVE_INFERENCE_PROFILE
    node = context['knowledge'][-1]
    edge = edge_premise()
    node['derivations'][0]['effective_edge_premises'] = [deepcopy(edge)]
    node['generation_origin'].update(knowledge_inference_profile=provenance.EFFECTIVE_INFERENCE_PROFILE,
        effective_edge_premises=[deepcopy(edge)])
    node['retrieval_support']['effective_edge_premises'] = [{'record_id': node['origin_record_id'], **deepcopy(edge)}]
    context['effective_edge_premises'] = deepcopy(node['retrieval_support']['effective_edge_premises'])
    return context


def lineage_state():
    context = mixed_context()
    nodes = context['knowledge']
    derived = deepcopy(nodes[-1]['derivations'][0])
    derived['derivation_depth'] = 1
    return {'revisions': {node['knode_revision_id']: deepcopy(node) for node in nodes},
        'by_record': {derived['record_id']: derived}, 'by_result': {uid(103): [derived]},
        'edges': {uid(103): [uid(101), uid(102)]},
        'groundings': {node['knode_revision_id']: deepcopy(node['groundings']) for node in nodes},
        'current_supports': {}, 'support_refs': {derived['record_id']: {uid(101): None, uid(102): None}},
        'edge_current': {(uid(500), 0): True}}


class EffectiveInferenceConsumersTests(unittest.TestCase):
    def test_loader_separates_frozen_edge_payload_from_sql_currentness(self):
        state = lineage_state()
        edge = edge_premise()
        derivation = deepcopy(state['by_record'][uid(1003)])
        derivation.pop('effective_edge_premises')
        derivation.pop('premise_revision_ids')
        def execute(sql):
            if sql.startswith('SELECT to_regclass'):
                row = {'relation': None if 'knowledge_data_groundings' in sql else 'present'}
                return SimpleNamespace(fetchone=lambda: row)
            if 'SELECT r.knode_revision_id' in sql:
                rows = list(state['revisions'].values())
            elif 'SELECT * FROM canonical_store.knowledge_derivations ' in sql:
                rows = [derivation]
            elif 'SELECT * FROM canonical_store.knowledge_derivation_premises ' in sql:
                rows = [{'record_id': uid(1003), 'premise_node_revision_id': uid(101)},
                        {'record_id': uid(1003), 'premise_node_revision_id': uid(102)}]
            elif 'k2k_edge_input_current' in sql:
                rows = [{'record_id': uid(1003), **{key: edge[key] for key in ('ordinal', 'execution_id', 'input_ordinal')},
                         'payload': {key: value for key, value in edge.items() if key not in ('ordinal', 'execution_id', 'input_ordinal')},
                         'current': False}]
            else:
                rows = []
            return SimpleNamespace(fetchall=lambda: deepcopy(rows))
        loaded = provenance.load(SimpleNamespace(execute=execute))
        self.assertEqual(loaded['by_record'][uid(1003)]['effective_edge_premises'], [edge])
        self.assertIs(loaded['edge_current'][(uid(500), 0)], False)
        self.assertNotIn('current', json.dumps(loaded['by_record'][uid(1003)]['effective_edge_premises']))

    def test_edge_invalidity_stales_route_without_changing_node_support_signature_or_history(self):
        state = lineage_state()
        original = deepcopy(state['by_record'])
        before = provenance.describe(state, uid(103))
        expected = sha256(json.dumps(provenance.current_route(state, uid(103))['records'], sort_keys=True).encode()).hexdigest()
        self.assertEqual(before['current_support_signature'], expected)
        state['edge_current'][(uid(500), 0)] = False
        after = provenance.describe(state, uid(103))
        self.assertEqual(after['current_support_signature'], before['current_support_signature'])
        self.assertEqual(after['current_applicability'], 'needs_revalidation')
        self.assertEqual(after['current_stale_premise_revision_ids'], [])
        self.assertEqual(after['current_stale_effective_edge_refs'][0]['execution_id'], uid(500))
        self.assertEqual(after['derivations'][0]['current_applicability'], 'needs_revalidation')
        self.assertEqual(state['by_record'], original)

    def test_invalid_ancestor_edge_reaches_descendant_without_fake_direct_information(self):
        state = lineage_state()
        child = deepcopy(state['by_record'][uid(1003)])
        child.update(record_id=uid(1004), result_node_revision_id=uid(104), premise_revision_ids=[uid(103), uid(102)], derivation_depth=2)
        child.pop('effective_edge_premises')
        state['by_record'][uid(1004)] = child
        state['by_result'][uid(104)] = [child]
        state['revisions'][uid(104)] = {'knode_revision_id': uid(104), 'origin_record_id': uid(1004), 'current_revision_id': uid(104)}
        state['edges'][uid(104)] = [uid(103), uid(102)]
        state['support_refs'][uid(1004)] = {uid(103): uid(1003), uid(102): None}
        state['edge_current'][(uid(500), 0)] = False
        result = provenance.describe(state, uid(104))
        self.assertEqual(result['current_applicability'], 'needs_revalidation')
        self.assertEqual(result['direct_groundings'], [])
        self.assertEqual({row['node_revision_id'] for row in result['current_transitive_source_refs']}, {uid(101), uid(102)})
        self.assertEqual(result['current_stale_effective_edge_refs'][0]['record_id'], uid(1003))

    def test_fresh_node_only_support_restores_same_revision_and_keeps_mixed_origin(self):
        state = lineage_state()
        before = provenance.describe(state, uid(103))
        fresh = deepcopy(state['by_record'][uid(1003)])
        fresh.update(record_id=uid(1010))
        fresh.pop('effective_edge_premises')
        state['by_record'][uid(1010)] = fresh
        state['by_result'][uid(103)].append(fresh)
        state['current_supports'][uid(103)] = {'record_id': uid(1010), 'node_revision_id': uid(103)}
        state['support_refs'][uid(1010)] = {uid(101): None, uid(102): None}
        state['edge_current'][(uid(500), 0)] = False
        result = provenance.describe(state, uid(103))
        self.assertEqual(result['current_applicability'], 'current_premises')
        self.assertEqual(result['current_effective_edge_refs'], [])
        self.assertEqual(result['origin_effective_edge_refs'], before['origin_effective_edge_refs'])
        self.assertEqual(result['generation_origin'], before['generation_origin'])
        self.assertNotEqual(result['current_support_signature'], before['current_support_signature'])

    def test_legacy_node_route_has_no_edge_fields_or_new_signature(self):
        state = lineage_state()
        state['by_record'][uid(1003)].pop('effective_edge_premises')
        before = deepcopy(state)
        state.pop('edge_current')
        self.assertEqual(provenance.describe(state, uid(103)), provenance.describe(before, uid(103)))
        self.assertEqual(set(provenance.current_route(state, uid(103))), {'records', 'stale_revision_ids'})
        self.assertNotIn('knowledge_inference_profile', provenance.describe(state, uid(103)))

    def test_query_keeps_exact_edge_input_in_citation_and_independent_validation(self):
        context = mixed_context()
        before = deepcopy(context)
        answer = wiki_query.normalize_answer(inferred_proposal(), context)
        citation = answer['claims'][0]['knowledge_evidence'][0]
        self.assertEqual(citation['effective_edge_premises'], context['effective_edge_premises'])
        self.assertEqual(answer['knowledge_inference_profile'], provenance.EFFECTIVE_INFERENCE_PROFILE)
        self.assertIn('not direct I/D quotes', wiki_query.generation_prompt(context))
        self.assertIn('full selected Node and Edge premises', wiki_query.validation_prompt(context, answer))
        rendered = wiki_query.render_answer(answer, wiki_query.validate_answer(decision(answer), answer))
        self.assertIn(uid(502), rendered)
        self.assertEqual(context, before)

    def test_query_reuses_every_registered_relation_predicate_without_reinterpreting_it(self):
        for predicate in ('supports', 'contradicts', 'qualifies', 'composes'):
            context = mixed_context()
            node = context['knowledge'][-1]
            for edge in (node['derivations'][0]['effective_edge_premises'][0],
                         node['generation_origin']['effective_edge_premises'][0],
                         node['retrieval_support']['effective_edge_premises'][0],
                         context['effective_edge_premises'][0]):
                edge['predicate'] = predicate
            with self.subTest(predicate=predicate):
                answer = wiki_query.normalize_answer(inferred_proposal(), context)
                self.assertEqual(answer['claims'][0]['knowledge_evidence'][0]['effective_edge_premises'][0]['predicate'], predicate)

    def test_query_refuses_missing_partial_stale_forged_or_unmarked_edge_delivery(self):
        for mutation in ('missing_inventory', 'missing_marker', 'wrong_event', 'missing_endpoint', 'stale', 'extra_inventory', 'missing_support_inventory'):
            context = mixed_context()
            node = context['knowledge'][-1]
            if mutation == 'missing_inventory':
                context['effective_edge_premises'] = []
            elif mutation == 'missing_marker':
                context.pop('knowledge_inference_profile')
                context.pop('effective_edge_premises')
            elif mutation == 'wrong_event':
                context['effective_edge_premises'][0]['effective_edge_ref']['applicability_basis_ref'] = uid(999)
            elif mutation == 'missing_endpoint':
                context['knowledge'].pop(0)
            elif mutation == 'stale':
                node['derivations'][0]['stale_effective_edge_refs'] = [edge_premise()]
            elif mutation == 'extra_inventory':
                context['effective_edge_premises'].append({**edge_premise(), 'record_id': uid(999)})
            else:
                node['retrieval_support'].pop('effective_edge_premises')
            with self.subTest(mutation=mutation), self.assertRaises(PalimpsestError):
                wiki_query.generation_schema(context)

    def test_malformed_new_edge_context_returns_structured_failure(self):
        for field in ('retrieval_support', 'support_edges', 'derivation_edges'):
            context = mixed_context()
            node = context['knowledge'][-1]
            if field == 'retrieval_support':
                node[field] = None
            elif field == 'support_edges':
                node['retrieval_support']['effective_edge_premises'] = None
            else:
                node['derivations'][0]['effective_edge_premises'] = None
            with self.subTest(field=field), self.assertRaises(PalimpsestError):
                wiki_query.generation_schema(context)

    def test_query_valid_selected_support_does_not_require_historical_origin_still_current(self):
        context = mixed_context()
        node = context['knowledge'][-1]
        old = node['derivations'][0]
        fresh = deepcopy(old)
        fresh.update(record_id=uid(1100))
        fresh.pop('effective_edge_premises')
        node['derivations'].append(fresh)
        old['current_applicability'] = 'needs_revalidation'
        detail = deepcopy(node['retrieval_support']['records'][-1])
        detail.update(record_id=uid(1100), derivation=fresh)
        node['retrieval_support']['records'][-1] = detail
        node['retrieval_support'].update(record_id=uid(1100), effective_edge_premises=[])
        context['effective_edge_premises'] = []
        answer = wiki_query.normalize_answer(inferred_proposal(), context)
        citation = answer['claims'][0]['knowledge_evidence'][0]
        self.assertEqual(citation['generation_origin']['origin_record_id'], uid(1003))
        self.assertEqual(citation['retrieval_support']['record_id'], uid(1100))
        self.assertEqual(citation['effective_edge_premises'], [])
        wiki_query.validation_prompt(context, answer)

    def test_retrieval_requires_all_endpoints_and_keeps_exact_selected_edges_only(self):
        graph, units, records = retrieval_fixture()
        inferred = graph['nodes'][-1]
        premises = inferred['derivations'][0]['premise_revision_ids']
        edge = edge_premise(*premises)
        inferred['derivations'][0]['effective_edge_premises'] = [edge]
        inferred['current_effective_edge_refs'] = [{'qualifiers': {'scope': 'UNDELIVERED_EDGE_SENTINEL'}}]
        documents, nodes = knowledge_projection(graph, units, records, None, set())
        selected = next(node for node in nodes if node['knode_revision_id'] == inferred['knode_revision_id'])
        self.assertEqual(selected['retrieval_support']['effective_edge_premises'], [{'record_id': records[-1]['record_id'], **edge}])
        self.assertNotIn('UNDELIVERED_EDGE_SENTINEL', json.dumps((documents, nodes)))
        edge['effective_edge_ref']['to_knode_revision_id'] = uid(999)
        _, nodes = knowledge_projection(graph, units, records, None, set())
        self.assertNotIn(inferred['knode_revision_id'], {node['knode_revision_id'] for node in nodes})

    def test_unselected_historical_edge_text_is_hash_only_without_rewriting_origin(self):
        graph, units, records = retrieval_fixture()
        inferred = graph['nodes'][-1]
        edge = edge_premise(*inferred['derivations'][0]['premise_revision_ids'])
        edge['qualifiers']['scope'] = 'UNDELIVERED_HISTORICAL_EDGE_SENTINEL'
        inferred['derivations'][0].update(effective_edge_premises=[deepcopy(edge)], current_applicability='needs_revalidation')
        inferred['generation_origin']['effective_edge_premises'] = [deepcopy(edge)]
        inferred['origin_effective_edge_refs'] = [deepcopy(edge)]
        old = deepcopy(graph)
        fresh = deepcopy(inferred['derivations'][0])
        fresh.update(record_id=uid(9100), current_applicability='current_premises')
        fresh['effective_edge_premises'][0]['qualifiers']['scope'] = 'Selected explicit relation'
        inferred['derivations'].append(fresh)
        records.append({'record_id': uid(9100), 'record_type': 'k2k',
                        'result_node_revision_id': inferred['knode_revision_id'], 'information_ids': []})
        documents, nodes = knowledge_projection(graph, units, records, None, set())
        selected = next(node for node in nodes if node['knode_revision_id'] == inferred['knode_revision_id'])
        self.assertNotIn('UNDELIVERED_HISTORICAL_EDGE_SENTINEL', json.dumps((documents, nodes)))
        self.assertEqual(selected['origin_effective_edge_refs'][0]['qualifiers_sha256'], digest(edge['qualifiers']))
        self.assertEqual(selected['retrieval_support']['effective_edge_premises'][0]['qualifiers']['scope'], 'Selected explicit relation')
        self.assertEqual(inferred['generation_origin'], old['nodes'][-1]['generation_origin'])

    def test_desktop_exact_edge_inputs_require_all_owned_endpoint_nodes(self):
        for outside in (False, True):
            context = mixed_context()
            node = context['knowledge'][-1]
            service = desktop_read.DesktopReadService.__new__(desktop_read.DesktopReadService)
            service.dsn = 'postgresql://unused'
            service._knowledge_scope = lambda: ([], [context['sources'][0]['data_id']])
            service._allowed_knowledge = lambda conn, ref, owners: not (outside and ref == uid(102))
            conn = MagicMock()
            conn.__enter__.return_value = conn
            def execute(sql, values=None):
                if 'WHERE knode_revision_id=%s' in sql:
                    value = deepcopy(node)
                    value['current_revision_id'] = uid(900)  # Historical view needs no global relation read.
                    value['transitive_source_refs'] = []
                elif 'k_explicit_source_decisions' in sql or sql.startswith('SET TRANSACTION'):
                    value = None
                elif 'WHERE r.knode_revision_id=ANY' in sql:
                    value = context['knowledge'][:-1]
                elif 'SELECT g.*,i.data_id' in sql:
                    value = []
                else:
                    raise AssertionError(sql)
                return SimpleNamespace(fetchone=lambda: value, fetchall=lambda: value)
            conn.execute.side_effect = execute
            metadata = {'derivations': node['derivations'], 'generation_origin': node['generation_origin']}
            with self.subTest(outside=outside), patch.object(desktop_read, 'connection', return_value=conn), \
                    patch.object(provenance, 'load', return_value={}), patch.object(provenance, 'describe', return_value=metadata), \
                    patch.object(desktop_read.version_provenance, 'load', return_value=None), \
                    patch.object(desktop_read.version_provenance, 'annotate', return_value={}), \
                    patch.object(desktop_read.version_provenance, 'graph_view', return_value={}):
                if outside:
                    with self.assertRaises(PalimpsestError) as raised:
                        service.knowledge_node(uid(103))
                    self.assertEqual(raised.exception.code, 'desktop_knowledge_not_in_wiki')
                else:
                    result = service.knowledge_node(uid(103))
                    self.assertEqual(result['premise_edges'], context['effective_edge_premises'])
                    self.assertEqual({row['knode_revision_id'] for row in result['premise_nodes']}, {uid(101), uid(102)})


@unittest.skipUnless(sys.platform == 'linux', 'Requires actual Linux projection filesystem')
class EffectiveInferenceQueryRuntimeTests(unittest.TestCase):
    def test_selected_edge_delivery_is_frozen_and_both_receipts_are_required(self):
        case = runtime_fixture.WikiQueryRuntimeTests('runTest')
        case.setUp()
        self.addCleanup(case.doCleanups)
        context = mixed_context()
        for unit in context['information']:
            unit['media'] = []
        corpus = case.runtime.retrieval.value['corpus']
        corpus.update({key: deepcopy(context[key]) for key in ('knowledge', 'information', 'sources', 'source_version_snapshot', 'knowledge_inference_profile')})
        corpus['projection_profile'] = {'schema_version': 'wiki-accepted-support-v1'}
        node = context['knowledge'][-1]
        corpus['documents'] = [{'document_id': 'k/' + uid(103), 'kind': 'knowledge',
            'knode_revision_id': uid(103), 'text': node['statement'], 'information_ids': []}]
        case.prepare()
        case.run_search()
        job = case.runtime.show(case.identifier)
        frozen = case.runtime.store.read_json(job['context_path'])
        self.assertEqual(frozen['effective_edge_premises'], context['effective_edge_premises'])
        self.assertEqual(len(frozen['knowledge']), 3)
        self.assertEqual(len(frozen['information']), 2)
        for phase in ('generator', 'validator'):
            response = (inferred_proposal() if phase == 'generator' else decision(
                case.runtime.store.read_json(job['last_proposal_path'])))
            value = runtime_fixture.exchange(case.runtime, case.identifier, phase, response)
            value['receipt']['delivered_knowledge_revision_ids'] = [row['knode_revision_id'] for row in frozen['knowledge']]
            operation = case.runtime.stage if phase == 'generator' else case.runtime.decide
            with self.assertRaises(PalimpsestError) as raised:
                operation(case.identifier, value)
            self.assertEqual(raised.exception.code, 'wiki_query_edge_delivery_mismatch')
            value['receipt']['delivered_effective_edge_premises'] = deepcopy(frozen['effective_edge_premises'])
            job = operation(case.identifier, value)
        self.assertEqual(job['state'], 'answered')
        self.assertEqual(case.runtime.original_reads, [])


if __name__ == '__main__':
    unittest.main()
