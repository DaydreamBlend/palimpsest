"""Pure selected-support and mocked freshness checks; no model or PostgreSQL."""

from copy import deepcopy
import json
from unittest.mock import MagicMock, patch
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.wiki_retrieval import (WikiRetrieval, knowledge_projection,
    information_document, projection_profile, source_version_snapshot, source_version_status)


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def node(number, *, premises=None):
    revision, record = uid(number), uid(10000 + number)
    result = {'knode_id': uid(20000 + number), 'knode_revision_id': revision,
        'current_revision_id': revision, 'origin_record_id': record,
        'statement': f'Synthetic claim {number}', 'identity_scope': 'general',
        'current_applicability': 'current_premises', 'data_version_supports': [],
        'generation_origin': {'origin_operation': 'i2k', 'is_inferred': False,
                              'origin_record_id': record}}
    if premises is not None:
        result['derivations'] = [{'record_id': record, 'result_node_revision_id': revision,
            'premise_revision_ids': list(premises), 'inference_type': 'deductive',
            'assumptions': ['Synthetic scope'], 'limitations': ['No actual model evaluation'],
            'derivation_basis': 'Synthetic transitivity', 'validation': {'verdict': 'accepted'},
            'current_applicability': 'current_premises'}]
        result['generation_origin'] = {'origin_operation': 'k2k', 'is_inferred': True,
            'origin_record_id': record, 'premise_revision_ids': list(premises)}
    return result


def record(value, information_ids=()):
    return {'record_id': value['origin_record_id'], 'result_node_revision_id': value['knode_revision_id'],
            'record_type': value['generation_origin']['origin_operation'], 'information_ids': list(information_ids)}


def fixture():
    units = {uid(n): {'information_id': uid(n), 'data_id': str(n) * 64,
        'source_execution_id': uid(300 + n), 'content': 'Actual source quote'} for n in (1, 2)}
    first, second, inferred = node(11), node(12), node(13, premises=[uid(11), uid(12)])
    graph = {'nodes': [first, second, inferred], 'groundings': [
        {'grounding_id': uid(30 + n), 'information_id': uid(n), 'node_revision_id': uid(10 + n),
         'data_id': str(n) * 64, 'origin_record_id': uid(10010 + n), 'quote': 'Actual source quote'}
        for n in (1, 2)]}
    return graph, units, [record(first, [uid(1)]), record(second, [uid(2)]), record(inferred)]


def version_state():
    series = uid(500)
    versions = {uid(501): {'version_id': uid(501), 'series_id': series, 'data_id': '1' * 64},
                uid(502): {'version_id': uid(502), 'series_id': series, 'data_id': '2' * 64},
                uid(503): {'version_id': uid(503), 'series_id': series, 'data_id': '1' * 64}}
    return {'versions': versions, 'heads': {series: uid(503)}, 'by_revision': {}, 'by_edge_revision': {}}


def bind(state, value, record_id, version_id):
    operation = 'k2k' if value['generation_origin']['is_inferred'] else 'i2k'
    support = {'record_id': record_id, 'operation': operation, 'version_ids': [version_id]}
    state['by_revision'].setdefault(value['knode_revision_id'], []).append(support)
    value['data_version_supports'].append({**support, 'versions': [state['versions'][version_id]]})


class WikiInferenceProjectionTests(unittest.TestCase):
    def test_contested_knowledge_stays_searchable_without_opponent_metadata_or_text_in_embedding(self):
        graph, units, records = fixture()
        graph['nodes'][0]['epistemic_projection'] = 'contested'
        graph['edges'] = [{'predicate': 'contradicts', 'opponent_statement': 'UNDISCLOSED_OPPONENT_SENTINEL'}]
        before = deepcopy(graph)
        documents, knowledge = knowledge_projection(graph, units, records, None, set())
        disputed = next(node for node in knowledge if node['knode_revision_id'] == graph['nodes'][0]['knode_revision_id'])
        document = next(doc for doc in documents if doc['knode_revision_id'] == disputed['knode_revision_id'])
        self.assertEqual(disputed['epistemic_projection'], 'contested')
        self.assertEqual(document['text'], disputed['statement'])
        self.assertNotIn('UNDISCLOSED_OPPONENT_SENTINEL', json.dumps((documents, knowledge)))
        self.assertEqual(graph, before)

    def test_other_current_support_quotes_do_not_escape_selected_retrieval_route(self):
        graph, units, records = fixture()
        node = graph['nodes'][-1]
        node.update(current_support_record_id=uid(99), current_support_signature='f' * 64,
            current_transitive_source_refs=[{'data_id': '9' * 64, 'quote': 'UNDELIVERED_CURRENT_I_SENTINEL'}],
            current_transitive_data_refs=[{'data_id': '9' * 64, 'quote': 'UNDELIVERED_CURRENT_D_SENTINEL'}])
        before = deepcopy(graph)
        documents, knowledge = knowledge_projection(graph, units, records, None, set())
        selected = next(value for value in knowledge if value['knode_revision_id'] == node['knode_revision_id'])
        self.assertEqual(selected['current_support_record_id'], uid(99))
        self.assertEqual(selected['current_support_signature'], 'f' * 64)
        self.assertNotIn('current_transitive_source_refs', selected)
        self.assertNotIn('current_transitive_data_refs', selected)
        self.assertNotIn('UNDELIVERED_CURRENT_', json.dumps((documents, knowledge)))
        self.assertTrue(selected['retrieval_support']['records'])
        self.assertEqual(graph, before)

    def test_empty_native_member_and_whitespace_information_are_searchable_metadata_without_source_rewrite(self):
        for content, description in (('', 'empty'), ('\r\n \t', 'whitespace-only')):
            unit = {'information_id': uid(1), 'data_id': '1' * 64, 'source_execution_id': uid(301),
                'title': 'src/package/__init__.py — definitions', 'content': content, 'media': [],
                'code_context': [{'representation_role': 'source_member', 'member_path': 'src/package/__init__.py'}],
                'source_refs': [{'locator_type': 'text_range', 'text_range': {'char_start': 9, 'char_end': 9 + len(content)}}]}
            before = deepcopy(unit)
            with self.subTest(content=content):
                document = information_document(unit)
                self.assertEqual(unit, before)
                self.assertEqual(document['information_ids'], [unit['information_id']])
                self.assertEqual(document['document_id'], 'i/' + uid(1))
                self.assertEqual(document['text_origin'], 'retained_source_metadata_descriptor')
                self.assertEqual(document['text'], unit['title'] + f'\n[Information metadata; {description} source text]')
                request = WikiRetrieval.embedding_request({'documents': [document]})
                self.assertTrue(request['documents'][0]['text'].strip())
                self.assertEqual(request['documents'][0]['document_id'], 'i/' + uid(1))
        untitled = information_document({**before, 'title': '', 'content': ''})
        self.assertEqual(untitled['text'], 'Information\n[Information metadata; empty source text]')

    def test_information_text_and_image_descriptor_keep_the_existing_projection_contract(self):
        unit = {'information_id': uid(1), 'content': '  # Cafe\u0301\r\n', 'title': 'Module', 'media': []}
        document = information_document(unit)
        self.assertEqual(document['text'], unit['content'])
        self.assertEqual(document['text_origin'], 'information_content')
        image = information_document({**unit, 'content': '', 'title': '', 'media': [{'sha256': 'a' * 64}]})
        self.assertEqual(image['text'], 'Image Information\n[Image media; no source transcription]')
        self.assertEqual(image['text_origin'], 'retained_media_title_descriptor')

    def test_derived_hit_keeps_exact_premises_and_transitive_leaves_without_direct_grounding(self):
        graph, units, records = fixture()
        before = deepcopy((graph, units, records))
        documents, knowledge = knowledge_projection(graph, units, list(reversed(records)), None, set())
        self.assertEqual((graph, units, records), before)
        inferred = next(n for n in knowledge if n['knode_revision_id'] == uid(13))
        self.assertEqual(inferred['retrieval_basis'], 'system_inference')
        self.assertEqual(inferred['groundings'], [])
        self.assertEqual(inferred['direct_groundings'], [])
        self.assertEqual({g['node_revision_id'] for g in inferred['transitive_source_refs']}, {uid(11), uid(12)})
        self.assertEqual(inferred['retrieval_support']['premise_revision_ids'], [uid(11), uid(12)])
        self.assertEqual(len(inferred['retrieval_support']['records']), 3)
        derivation = next(r for r in inferred['retrieval_support']['records'] if r['operation'] == 'k2k')
        self.assertEqual(derivation['information_ids'], [])
        self.assertEqual(derivation['derivation']['limitations'], ['No actual model evaluation'])
        self.assertEqual(next(d for d in documents if d['knode_revision_id'] == uid(13))['information_ids'],
                         [uid(1), uid(2)])

    def test_unused_additional_direct_support_does_not_deliver_its_information_through_node_metadata(self):
        graph, units, records = fixture()
        units[uid(3)] = {'information_id': uid(3), 'data_id': '3' * 64,
                        'source_execution_id': uid(303), 'content': 'An independently accepted source support.'}
        extra = {'grounding_id': uid(33), 'information_id': uid(3), 'node_revision_id': uid(13),
                 'data_id': '3' * 64, 'origin_record_id': uid(10090), 'quote': units[uid(3)]['content']}
        graph['groundings'].append(extra)
        records.append({'record_id': uid(10090), 'record_type': 'i2k',
                        'result_node_revision_id': uid(13), 'information_ids': [uid(3)]})
        before = deepcopy(graph)
        documents, knowledge = knowledge_projection(graph, units, records, None, set())
        inferred = next(n for n in knowledge if n['knode_revision_id'] == uid(13))
        selected = next(d for d in documents if d['knode_revision_id'] == uid(13))
        self.assertEqual(inferred['retrieval_support']['operation'], 'k2k')
        self.assertEqual(selected['information_ids'], [uid(1), uid(2)])
        self.assertEqual(inferred['groundings'], [])
        self.assertEqual(inferred['direct_groundings'], [])
        self.assertNotIn(extra, inferred['transitive_source_refs'])
        self.assertEqual(graph, before)

    def test_missing_source_or_review_required_premise_cannot_form_partial_derivation(self):
        for mutation in ('missing_information', 'review_required', 'stale_premise', 'historical_revision'):
            graph, units, records = fixture()
            excluded = set()
            if mutation == 'missing_information':
                del units[uid(2)]
                graph['groundings'].pop()
            elif mutation == 'review_required':
                excluded.add(uid(12))
            elif mutation == 'stale_premise':
                graph['nodes'][1]['current_applicability'] = 'needs_revalidation'
            else:
                graph['nodes'][1]['current_revision_id'] = uid(99)
            with self.subTest(mutation=mutation):
                _, knowledge = knowledge_projection(graph, units, records, None, excluded)
                self.assertEqual([n['knode_revision_id'] for n in knowledge], [uid(11)])

    def test_multi_source_terminal_requires_all_actual_information_even_when_one_quote_matches(self):
        graph, units, records = fixture()
        records[0]['information_ids'].append(uid(2))
        del units[uid(2)]
        graph['groundings'].pop()
        self.assertEqual(knowledge_projection(graph, units, records, None, set()), ([], []))

    def test_an_independent_accepted_reuse_route_can_cover_selected_source(self):
        graph, units, records = fixture()
        records[0]['information_ids'].append(uid(2))
        graph['groundings'][1]['node_revision_id'] = uid(11)
        del units[uid(1)]
        graph['groundings'].pop(0)
        reuse = {**records[0], 'record_id': uid(900), 'information_ids': [uid(2)]}
        _, knowledge = knowledge_projection(graph, units, records + [reuse], None, set())
        self.assertEqual([n['knode_revision_id'] for n in knowledge], [uid(11)])
        self.assertEqual(knowledge[0]['retrieval_support']['record_id'], uid(900))
        self.assertEqual(knowledge[0]['generation_origin']['origin_record_id'], records[0]['record_id'])

    def test_same_data_revert_requires_current_bound_support_and_retains_inference_origin(self):
        graph, units, records = fixture()
        units[uid(2)]['data_id'] = '1' * 64
        graph['groundings'][1]['data_id'] = '1' * 64
        state = version_state()
        original_origin = deepcopy(graph['nodes'][2]['generation_origin'])
        for value in graph['nodes']:
            bind(state, value, value['origin_record_id'], uid(501))
        self.assertEqual(knowledge_projection(graph, units, records, state, set()), ([], []))
        current_records = []
        for ordinal, value in enumerate(graph['nodes']):
            current_id = uid(600 + ordinal)
            bind(state, value, current_id, uid(503))
            current_records.append({**records[ordinal], 'record_id': current_id})
            if ordinal == 2:
                value['derivations'].append({**deepcopy(value['derivations'][0]), 'record_id': current_id})
        _, knowledge = knowledge_projection(graph, units, records + current_records, state, set())
        inferred = next(n for n in knowledge if n['knode_revision_id'] == uid(13))
        self.assertEqual(inferred['retrieval_support']['record_id'], uid(602))
        self.assertEqual(inferred['generation_origin'], original_origin)
        self.assertEqual(inferred['source_version_status'], 'current')
        self.assertTrue(all(r['data_versions'][0]['version_id'] == uid(503)
                            for r in inferred['retrieval_support']['records']))
        graph['nodes'][2]['current_applicability'] = 'needs_revalidation'
        self.assertNotIn(uid(13), [n['knode_revision_id'] for n in
            knowledge_projection(graph, units, records + current_records, state, set())[1]])

    def test_historical_source_unbound_record_cannot_bypass_current_filter(self):
        graph, units, records = fixture()
        state = version_state()
        _, knowledge = knowledge_projection(graph, units, records, state, set())
        self.assertEqual([n['knode_revision_id'] for n in knowledge], [uid(11)])
        self.assertEqual(knowledge[0]['source_version_status'], 'untracked')
        self.assertEqual(source_version_status(state, '2' * 64), 'historical')

    def test_source_scope_and_extra_version_context_must_belong_to_selected_data(self):
        graph, units, records = fixture()
        graph['nodes'][0].update(identity_scope='source', source_data_id='9' * 64)
        _, knowledge = knowledge_projection(graph, units, records, None, set())
        self.assertEqual([n['knode_revision_id'] for n in knowledge], [uid(12)])
        state = version_state()
        state['versions'][uid(501)]['data_id'] = '9' * 64
        state['heads'][uid(500)] = uid(501)
        bind(state, graph['nodes'][1], records[1]['record_id'], uid(501))
        self.assertEqual(knowledge_projection(graph, units, records, state, set()), ([], []))

    def test_deep_derivation_chain_and_unfounded_cycle_have_no_depth_cutoff(self):
        graph, units, records = fixture()
        for number in range(14, 145):
            value = node(number, premises=[uid(number - 1), uid(11)])
            graph['nodes'].append(value)
            records.append(record(value))
        _, knowledge = knowledge_projection(graph, units, list(reversed(records)), None, set())
        self.assertEqual(len(knowledge), 134)
        last = next(n for n in knowledge if n['knode_revision_id'] == uid(144))
        self.assertEqual(len(last['retrieval_support']['records']), 134)
        self.assertEqual(len(last['transitive_source_refs']), 2)
        cycle = [node(800, premises=[uid(801)]), node(801, premises=[uid(800)])]
        self.assertEqual(knowledge_projection({'nodes': cycle, 'groundings': []}, units,
            [record(value) for value in cycle], None, set()), ([], []))

    def test_source_version_snapshot_preserves_matching_versions_and_dynamic_heads_separately(self):
        state = version_state()
        before = source_version_snapshot(state, {'1' * 64})
        self.assertEqual([v['version_id'] for v in before['versions']], [uid(501), uid(503)])
        state['heads'][uid(500)] = uid(502)
        after = source_version_snapshot(state, {'1' * 64})
        self.assertEqual(before['versions'], after['versions'])
        self.assertNotEqual(before['heads'], after['heads'])

    def test_i2k_full_execution_context_does_not_fabricate_extra_candidate_source_dependencies(self):
        graph, units, records = fixture()
        del units[uid(2)]
        graph['groundings'].pop()
        state = version_state()
        extra = {'version_id': uid(701), 'series_id': uid(700), 'data_id': '9' * 64}
        state['versions'][uid(701)] = extra
        state['heads'][uid(700)] = uid(701)
        first = graph['nodes'][0]
        bind(state, first, records[0]['record_id'], uid(503))
        first['data_version_supports'][0]['versions'].append(extra)
        first['data_version_supports'][0]['version_ids'].append(uid(701))
        _, knowledge = knowledge_projection(graph, units, records, state, set())
        self.assertEqual(len(knowledge), 1)
        self.assertEqual(knowledge[0]['retrieval_support']['source_data_ids'], ['1' * 64])
        self.assertEqual(len(knowledge[0]['retrieval_support']['records'][0]['data_versions']), 2)
        frozen = source_version_snapshot(state, {'1' * 64}, {uid(700)})
        self.assertEqual(frozen['heads'][uid(700)], uid(701))
        state['heads'][uid(700)] = uid(702)
        self.assertNotEqual(frozen, source_version_snapshot(state, {'1' * 64}, {uid(700)}))
        self.assertEqual(knowledge_projection(graph, units, records, state, set()), ([], []))

    def test_index_requires_matching_projection_and_version_heads_but_history_remains_readable(self):
        state = version_state()
        corpus = {'knowledge_state_version': 4, 'sources': [{'data_id': '1' * 64}],
            'projection_profile': projection_profile(), 'source_version_snapshot': source_version_snapshot(state, {'1' * 64})}
        stored = {'wiki_id': uid(91), 'import_id': uid(92), 'corpus': corpus,
                  'corpus_sha256': digest(corpus), 'profile': {}, 'profile_sha256': digest({})}
        conn = MagicMock()
        conn.execute.return_value.fetchone.side_effect = lambda: stored
        retrieval = WikiRetrieval('unused', 'unused')
        retrieval.database = MagicMock()
        retrieval.database._head.return_value = uid(92)

        def execute(sql, args=None):
            result = MagicMock()
            result.fetchone.return_value = {'version': 4} if 'SELECT version' in sql else stored
            return result

        conn.execute.side_effect = execute
        with patch('palimpsest.wiki_retrieval.connection') as connection, \
                patch.object(retrieval, '_source_versions', return_value=corpus['source_version_snapshot']) as snapshot:
            connection.return_value.__enter__.return_value = conn
            self.assertEqual(retrieval.index(uid(93))['corpus'], corpus)
            snapshot.return_value = {**corpus['source_version_snapshot'], 'heads': {uid(500): uid(502)}}
            with self.assertRaises(PalimpsestError) as caught:
                retrieval.index(uid(93))
            self.assertEqual(caught.exception.code, 'retrieval_index_stale')
            self.assertEqual(retrieval.index(uid(93), current=False)['corpus'], corpus)
            snapshot.return_value = corpus['source_version_snapshot']
            del corpus['projection_profile']
            stored['corpus_sha256'] = digest(corpus)
            with self.assertRaises(PalimpsestError) as caught:
                retrieval.index(uid(93))
            self.assertEqual(caught.exception.code, 'retrieval_index_stale')
            self.assertEqual(retrieval.index(uid(93), current=False)['corpus'], corpus)


if __name__ == '__main__':
    unittest.main()
