"""Scoped current-status views and versioned query guidance; no DB/model calls."""

from copy import deepcopy
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from palimpsest import desktop_read, edge_projection, wiki_query
from palimpsest.desktop_read import DesktopReadService
from palimpsest.errors import PalimpsestError
from test_edge_projection import fixture, uid
import test_wiki_query_inference as inference_fixture
import test_wiki_query_runtime as runtime_fixture


class EpistemicQueryTests(unittest.TestCase):
    def test_new_marker_guides_both_calls_and_unresolved_conflict_cannot_be_accepted(self):
        context = inference_fixture.inference_context()
        old = deepcopy(context)
        before = wiki_query.generation_prompt(old)
        context['epistemic_projection_profile'] = edge_projection.PROFILE
        for node in context['knowledge']:
            node['epistemic_projection'] = 'contested'
        answer = wiki_query.normalize_answer(inference_fixture.inferred_proposal(), context)
        generated = wiki_query.generation_prompt(context)
        validated = wiki_query.validation_prompt(context, answer)
        for prompt in (generated, validated):
            self.assertIn('CURRENT EPISTEMIC PROJECTION', prompt)
            self.assertIn('no opposing statement', prompt)
            self.assertIn('does not run K2K on relationship premises', prompt)
            self.assertIn('conflicts_resolved=false', prompt)
        response = inference_fixture.decision(answer)
        response['conflicts_resolved'] = False
        with self.assertRaises(PalimpsestError) as raised:
            wiki_query.validate_answer(response, answer)
        self.assertEqual(raised.exception.code, 'wiki_query_unverified_acceptance')
        response['verdict'] = 'needs_review'
        self.assertEqual(wiki_query.validate_answer(response, answer)['verdict'], 'needs_review')
        self.assertNotIn('CURRENT EPISTEMIC PROJECTION', before)
        self.assertEqual(wiki_query.generation_prompt(old), before)

    def test_unknown_projection_and_missing_status_do_not_become_uncontested(self):
        context = inference_fixture.inference_context()
        context['epistemic_projection_profile'] = 'unknown-profile'
        with self.assertRaises(PalimpsestError):
            wiki_query.generation_schema(context)
        context['epistemic_projection_profile'] = edge_projection.PROFILE
        with self.assertRaises(PalimpsestError):
            wiki_query.generation_schema(context)


class DesktopEpistemicTests(unittest.TestCase):
    def service(self):
        service = DesktopReadService.__new__(DesktopReadService)
        service.dsn = 'postgresql://unused'
        service._knowledge_scope = lambda: ([], ['a' * 64])
        service._allowed_knowledge = lambda *args: True
        return service

    def test_catalog_keeps_generic_status_but_not_other_source_node_details(self):
        nodes, edges = fixture()
        nodes[0].update(source_data_ids=['a' * 64], epistemic_projection='contested',
                        opposing_statement='PRIVATE_OPPONENT_SENTINEL')
        nodes[1].update(source_data_ids=['b' * 64], epistemic_projection='contested')
        conn = MagicMock()
        with patch.object(desktop_read, 'KnowledgeRuntime') as runtime, \
                patch.object(desktop_read, 'connection', return_value=conn), \
                patch.object(desktop_read.version_provenance, 'load', return_value=None):
            runtime.return_value.graph.return_value = {'nodes': nodes, 'edges': edges}
            result = self.service().knowledge_catalog()
        self.assertEqual(len(result['nodes']), 1)
        self.assertEqual(result['edges'], [])
        self.assertEqual(result['nodes'][0]['epistemic_projection'], 'contested')
        self.assertNotIn('PRIVATE_OPPONENT_SENTINEL', json.dumps(result))
        self.assertNotIn(nodes[1]['statement'], json.dumps(result))
        self.assertNotIn(nodes[1]['knode_id'], json.dumps(result))

    def test_catalog_lists_owned_n2e_edges_separately_from_nodes(self):
        nodes, edges = fixture('supports')
        for node in nodes:
            node.update(source_data_ids=['a' * 64], generation_origin={'origin_operation': 'i2k', 'is_inferred': False})
        edges[0].update(rationale='Recorded relation', qualifiers={'scope': 'fixture'},
                        applicability_status='applicable', applicable=True, usable=True)
        conn = MagicMock()
        with patch.object(desktop_read, 'KnowledgeRuntime') as runtime, \
                patch.object(desktop_read, 'connection', return_value=conn), \
                patch.object(desktop_read.version_provenance, 'load', return_value=None):
            runtime.return_value.graph.return_value = {'nodes': nodes, 'edges': edges}
            result = self.service().knowledge_catalog()
        self.assertEqual(len(result['nodes']), 2)
        self.assertEqual(len(result['edges']), 1)
        edge = result['edges'][0]
        self.assertEqual(edge['generation_origin']['origin_operation'], 'n2e')
        self.assertEqual((edge['from_statement'], edge['to_statement']),
                         (nodes[0]['statement'], nodes[1]['statement']))

    def test_detail_derives_current_status_but_does_not_rewrite_historical_projection(self):
        nodes, edges = fixture()
        for current in (True, False):
            with self.subTest(current=current):
                selected = {**deepcopy(nodes[0]), 'origin_record_id': uid(80),
                            'identity_scope': 'source', 'source_data_id': 'a' * 64}
                if not current:
                    selected['current_revision_id'] = uid(99)
                conn = MagicMock()
                def execute(query, values=None):
                    if 'WHERE knode_revision_id=%s' in query:
                        result = selected
                    elif 'k_explicit_source_decisions' in query:
                        result = None
                    elif 'SELECT g.*,i.data_id' in query:
                        result = []
                    elif query.startswith('SET TRANSACTION'):
                        result = None
                    else:
                        raise AssertionError('Unexpected detail SQL: ' + query)
                    return SimpleNamespace(fetchone=lambda: deepcopy(result), fetchall=lambda: deepcopy(result))
                conn.execute.side_effect = execute
                conn.__enter__.return_value = conn
                relations = [{**edges[0], 'effective_from_revision_id': uid(11),
                    'effective_to_revision_id': uid(12), 'applicable': True, 'usable': True}]
                with patch.object(desktop_read, 'connection', return_value=conn), \
                        patch.object(desktop_read.knowledge_provenance, 'load', return_value={}), \
                        patch.object(desktop_read.knowledge_provenance, 'describe', return_value={'derivations': []}), \
                        patch.object(desktop_read.version_provenance, 'load', return_value=None), \
                        patch.object(desktop_read.version_provenance, 'annotate', return_value={}), \
                        patch.object(desktop_read.version_provenance, 'graph_view', return_value={}), \
                        patch.object(desktop_read.KnowledgeRuntime, '_nodes', return_value=nodes), \
                        patch.object(desktop_read.KnowledgeRuntime, '_edges', return_value=edges), \
                        patch.object(desktop_read.edge_projection, 'resolve', return_value=relations) as resolve:
                    result = self.service().knowledge_node(uid(11))
                if current:
                    self.assertEqual(result['node']['epistemic_projection'], 'contested')
                    self.assertEqual(result['node']['epistemic_projection_scope'], 'current_graph')
                    resolve.assert_called_once()
                else:
                    self.assertNotIn('epistemic_projection', result['node'])
                    resolve.assert_not_called()
                self.assertEqual(result['node']['statement'], selected['statement'])
                self.assertEqual(result['node']['semantic_payload'], selected['semantic_payload'])


@unittest.skipUnless(sys.platform == 'linux', 'Requires real Linux projection files')
class QueryEpistemicContextTests(unittest.TestCase):
    def test_corpus_marker_is_frozen_into_query_context_without_opponent_expansion(self):
        case = runtime_fixture.WikiQueryRuntimeTests('runTest')
        case.setUp()
        self.addCleanup(case.doCleanups)
        corpus = case.runtime.retrieval.value['corpus']
        corpus['epistemic_projection_profile'] = edge_projection.PROFILE
        corpus['knowledge'][0]['epistemic_projection'] = 'contested'
        case.prepare()
        case.run_search()
        job = case.runtime.show(case.identifier)
        context = case.runtime.store.read_json(job['context_path'])
        self.assertEqual(context['epistemic_projection_profile'], edge_projection.PROFILE)
        self.assertEqual(context['knowledge'][0]['epistemic_projection'], 'contested')
        self.assertEqual(len(context['knowledge']), 1)
        self.assertEqual(case.runtime.original_reads, [])


if __name__ == '__main__':
    unittest.main()
