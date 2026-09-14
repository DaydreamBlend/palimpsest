"""Knowledge boundary checks; synthetic I/revisions, no semantic evaluation."""

from copy import deepcopy
import unittest

from palimpsest.errors import PalimpsestError
from palimpsest.knowledge import (NODE_SCHEMA, NODE_DECISION_SCHEMA, node_fingerprints,
                                 normalize_nodes, source_block_ranges, validate_node_decisions)
from palimpsest.n2e import (EDGE_SCHEMA, EDGE_DECISION_SCHEMA, edge_fingerprints,
                           normalize_edges, validate_edge_decisions)


def uid(number):
    return f'019947e2-1234-7000-8000-{number:012x}'


def fixture():
    semantic = {'subject': 'Device A', 'relation': 'has measured current', 'object': '3 μA',
                'polarity': 'positive', 'quantifier': 'sample mean', 'scope': 'bench test',
                'conditions': ['T = 20 °C'], 'time_range': ''}
    node = {'candidate_key': 'obs_1', 'kind': 'observation', 'statement': 'Current was 3 μA.',
            'semantic_payload': semantic, 'evidence': [{'information_id': uid(1),
                'quote': 'Cafe\u0301: μ = 3 μA.', 'media_sha256': 'a' * 64, 'source_role': 'figure'}],
            'uncertainties': []}
    packet = {'schema_version': 'i2k-input-v1', 'page_count': 2,
              'model_input': {'information': [
                  {'information_id': uid(1), 'content': 'Prefix. Cafe\u0301: μ = 3 μA. Suffix.',
                   'media': [{'sha256': 'a' * 64}]},
                  {'information_id': uid(2), 'content': 'Repeat. Repeat.',
                   'media': [{'sha256': 'b' * 64}]}]}}
    response = {'nodes': [node], 'source_requests': [], 'complete': True, 'coverage_notes': []}
    return packet, response


def decision(key, verdict='accepted', *, target=None, revision=None):
    return {'candidate_key': key, 'verdict': verdict, 'equivalent_candidate_key': target,
            'equivalent_revision_id': revision, 'reason_codes': ['source_supported'],
            'reason': 'The exact quoted result supports the scoped statement.'}


def add_block(unit, block, start, end, *, origin='parser_source'):
    unit.setdefault('source_refs', []).append({'block_id': block, 'page_index': 0,
        'raw_locator': block, 'anchor_sha256': 'c' * 64})
    segment = {'source_block_id': block, 'page_index': 0, 'raw_locator': block,
        'anchor_sha256': 'c' * 64, 'char_start': start, 'char_end': end,
        'source_char_range': [0, end - start], 'text_origin': origin}
    unit.setdefault('source_assembly', {'content_segments': []})['content_segments'].append(segment)
    return segment


class KnowledgeTests(unittest.TestCase):
    def error(self, code, call):
        with self.assertRaises(PalimpsestError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)

    def test_exact_quote_unicode_media_and_unchanged_input(self):
        packet, response = fixture()
        before = deepcopy((packet, response))
        node = normalize_nodes(response, packet)[0]
        citation = node['evidence'][0]
        self.assertEqual(citation['char_start'], 8)
        self.assertEqual(packet['model_input']['information'][0]['content'][
            citation['char_start']:citation['char_end']], 'Cafe\u0301: μ = 3 μA.')
        self.assertEqual(before, (packet, response))
        response['nodes'][0]['evidence'][0]['quote'] = 'Café: μ = 3 μA.'
        self.error('knowledge_quote_mismatch', lambda: normalize_nodes(response, packet))

    def test_quote_must_be_unique_and_media_must_belong_to_cited_i(self):
        packet, response = fixture()
        response['nodes'][0]['evidence'][0]['media_sha256'] = 'b' * 64
        self.error('invalid_knowledge_evidence', lambda: normalize_nodes(response, packet))
        response['nodes'][0]['evidence'][0].update(information_id=uid(2), quote='Repeat.')
        self.error('ambiguous_knowledge_quote', lambda: normalize_nodes(response, packet))
        response['nodes'][0]['evidence'][0]['information_id'] = uid(99)
        self.error('invalid_knowledge_evidence', lambda: normalize_nodes(response, packet))

    def test_block_address_preserves_unicode_and_latex_and_needs_explicit_opt_in(self):
        packet, response = fixture()
        unit = packet['model_input']['information'][0]
        unit['content'] = 'Lead. Cafe\u0301: $3\\,\\mathrm{\\mu m}^{2}$. End.'
        start, end = unit['content'].index('Cafe'), unit['content'].index(' End.')
        add_block(unit, '/body/result', start, end)
        response['nodes'][0]['evidence'] = [{'information_id': uid(1),
            'source_block_id': '/body/result', 'source_role': 'results'}]
        before = deepcopy((packet, response))
        self.error('invalid_knowledge_evidence', lambda: normalize_nodes(response, packet))
        citation = normalize_nodes(response, packet, allow_block_refs=True)[0]['evidence'][0]
        self.assertEqual(citation, {'information_id': uid(1), 'source_block_id': '/body/result',
            'source_role': 'results', 'quote': unit['content'][start:end], 'media_sha256': None,
            'char_start': start, 'char_end': end})
        self.assertEqual(before, (packet, response))

    def test_repeated_block_text_uses_its_own_range_without_substring_search(self):
        packet, response = fixture()
        unit = packet['model_input']['information'][1]
        add_block(unit, '/repeat/first', 0, 7)
        add_block(unit, '/repeat/second', 8, 15)
        response['nodes'][0]['evidence'] = [{'information_id': uid(2),
            'source_block_id': block, 'source_role': 'other'} for block in ('/repeat/first', '/repeat/second')]
        evidence = normalize_nodes(response, packet, allow_block_refs=True)[0]['evidence']
        self.assertEqual([citation['quote'] for citation in evidence], ['Repeat.', 'Repeat.'])
        self.assertEqual([citation['char_start'] for citation in evidence], [0, 8])
        response['nodes'][0]['evidence'].append(deepcopy(response['nodes'][0]['evidence'][1]))
        self.error('duplicate_knowledge_evidence', lambda: normalize_nodes(response, packet, allow_block_refs=True))

    def test_block_rejects_unknown_cross_information_and_model_offsets(self):
        packet, response = fixture()
        add_block(packet['model_input']['information'][0], '/owned/first', 0, 7)
        evidence = {'information_id': uid(2), 'source_block_id': '/owned/first', 'source_role': 'other'}
        response['nodes'][0]['evidence'] = [evidence]
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))
        evidence.update(information_id=uid(1), source_block_id='/missing')
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))
        evidence['source_block_id'] = '/owned/first'
        for field, value in (('char_start', 0), ('quote', 'Prefix.'), ('media_sha256', None)):
            evidence[field] = value
            self.error('invalid_knowledge_evidence', lambda: normalize_nodes(response, packet, allow_block_refs=True))
            del evidence[field]
        del evidence['source_role']
        self.error('invalid_knowledge_evidence', lambda: normalize_nodes(response, packet, allow_block_refs=True))

    def test_block_needs_exact_unambiguous_nonempty_source_metadata(self):
        packet, response = fixture()
        unit = packet['model_input']['information'][0]
        segment = add_block(unit, '/body/first', 0, 7)
        response['nodes'][0]['evidence'] = [{'information_id': uid(1),
            'source_block_id': '/body/first', 'source_role': 'other'}]
        for field, value in (('char_start', None), ('char_start', True), ('char_start', -1),
                             ('char_end', 0), ('char_end', len(unit['content']) + 1),
                             ('source_char_range', None), ('source_char_range', [0, 6]),
                             ('text_origin', 'derived_visual_reference'), ('raw_locator', '/another'),
                             ('anchor_sha256', 'd' * 64), ('page_index', 1)):
            changed = deepcopy(packet)
            changed['model_input']['information'][0]['source_assembly']['content_segments'][0][field] = value
            with self.subTest(field=field, value=value):
                self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, changed, allow_block_refs=True))
        for field in ('char_start', 'char_end', 'source_char_range', 'text_origin', 'raw_locator', 'anchor_sha256'):
            changed = deepcopy(packet)
            del changed['model_input']['information'][0]['source_assembly']['content_segments'][0][field]
            self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, changed, allow_block_refs=True))
        unit['source_assembly']['content_segments'].append(deepcopy(segment))
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))
        unit['source_assembly']['content_segments'].pop()
        unit['source_refs'] = []
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))

    def test_page_facsimile_labels_are_not_source_text_and_quote_path_is_unchanged(self):
        packet, response = fixture()
        old = normalize_nodes(response, packet)
        self.assertEqual(old, normalize_nodes(response, packet, allow_block_refs=True))
        unit = packet['model_input']['information'][0]
        unit['content'] = 'Original page 1'
        segment = add_block(unit, '/original_page_facsimile/0', 0, len(unit['content']),
                            origin='original_page_facsimile')
        response['nodes'][0]['evidence'] = [{'information_id': uid(1),
            'source_block_id': '/original_page_facsimile/0', 'source_role': 'figure'}]
        self.assertEqual(source_block_ranges(unit), {})
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))
        segment['text_origin'] = 'parser_source'
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))
        response['nodes'][0]['evidence'] = [{'information_id': uid(1), 'quote': '',
            'media_sha256': 'a' * 64, 'source_role': 'figure'}]
        citation = normalize_nodes(response, packet, allow_media_only=True, allow_block_refs=True)[0]['evidence'][0]
        self.assertEqual((citation['quote'], citation['char_start'], citation['char_end']), ('', 0, 0))

    def test_registered_markdown_span_is_supported_but_blank_or_missing_assembly_is_not(self):
        packet, response = fixture()
        unit = packet['model_input']['information'][0]
        unit['content'] = '# Methods\n\nA protocol with exact source spacing.\n'
        segment = add_block(unit, '/markdown/section/0', 0, len(unit['content']), origin='registered_source')
        segment['page_index'] = None
        del unit['source_refs'][0]['page_index']
        response['nodes'][0]['evidence'] = [{'information_id': uid(1),
            'source_block_id': '/markdown/section/0', 'source_role': 'methods'}]
        citation = normalize_nodes(response, packet, allow_block_refs=True)[0]['evidence'][0]
        self.assertEqual(citation['quote'], unit['content'])
        unit['content'] = ' ' * len(unit['content'])
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))
        del unit['source_assembly']
        self.error('invalid_knowledge_block_reference', lambda: normalize_nodes(response, packet, allow_block_refs=True))

    def test_fp_ignores_prose_and_source_role_preserves_meaning_changes(self):
        packet, response = fixture()
        original = normalize_nodes(response, packet)[0]
        changed = deepcopy(response)
        changed['nodes'][0]['statement'] = 'The observed current is 3 μA.'
        changed['nodes'][0]['evidence'][0]['source_role'] = 'results'
        second = normalize_nodes(changed, packet)[0]
        self.assertEqual(original['content_fingerprint'], second['content_fingerprint'])
        payload = deepcopy(original['semantic_payload'])
        payload['conditions'] = [' x ', 'T = 20 °C', 'x']
        first = node_fingerprints('observation', payload)
        payload['conditions'] = ['T = 20 °C', 'x']
        self.assertEqual(first, node_fingerprints('observation', payload))
        payload['scope'] = 'all devices'
        self.assertNotEqual(first, node_fingerprints('observation', payload))
        payload['subject'] = 'device a'
        self.assertNotEqual(node_fingerprints('observation', original['semantic_payload']),
                            node_fingerprints('observation', payload))

    def test_strict_envelopes_and_incomplete_source_requests(self):
        packet, response = fixture()
        response['nodes'][0]['knode_id'] = uid(99)
        self.error('invalid_knowledge_proposal', lambda: normalize_nodes(response, packet))
        del response['nodes'][0]['knode_id']
        response['source_requests'] = [{'information_ids': [uid(1)],
                                        'question': 'Is the unit μA?', 'page_numbers': [1]}]
        self.error('unresolved_knowledge_source_request', lambda: normalize_nodes(response, packet))
        response['complete'] = False
        self.assertEqual(len(normalize_nodes(response, packet)), 1)
        response['source_requests'][0]['page_numbers'] = [True]
        self.error('invalid_knowledge_source_request', lambda: normalize_nodes(response, packet))

    def test_reuse_orders_accepted_root_and_rejects_missing_or_cyclic_decisions(self):
        candidates = [{'candidate_key': key, 'kind': 'proposition'} for key in ('a', 'b', 'c')]
        value = {'complete': True, 'decisions': [decision('a', 'reused', target='b'),
                 decision('b', 'reused', target='c'), decision('c')]}
        self.assertEqual(list(validate_node_decisions(value, candidates, [])), ['c', 'b', 'a'])
        value['decisions'][2] = decision('c', 'reused', target='a')
        self.error('knowledge_reuse_cycle', lambda: validate_node_decisions(value, candidates, []))
        value['decisions'][2] = decision('c', 'rejected')
        self.error('invalid_knowledge_decision', lambda: validate_node_decisions(value, candidates, []))
        value['decisions'][2] = decision('c', 'reused', revision=uid(3))
        self.assertEqual(list(validate_node_decisions(value, candidates, [uid(3)])), ['c', 'b', 'a'])
        self.error('invalid_knowledge_decision', lambda: validate_node_decisions(value, candidates, [uid(4)]))
        value['decisions'].pop()
        self.error('invalid_knowledge_decision', lambda: validate_node_decisions(value, candidates, []))

    def test_reuse_may_not_target_self_or_other_kind_or_duplicate_decision(self):
        candidates = [{'candidate_key': 'a', 'kind': 'proposition'},
                      {'candidate_key': 'b', 'kind': 'observation'}]
        value = {'complete': True, 'decisions': [decision('a', 'reused', target='b'), decision('b')]}
        self.error('invalid_knowledge_decision', lambda: validate_node_decisions(value, candidates, []))
        value['decisions'][0]['equivalent_candidate_key'] = 'a'
        self.error('invalid_knowledge_decision', lambda: validate_node_decisions(value, candidates, []))
        value['decisions'] = [decision('a'), decision('a')]
        self.error('invalid_knowledge_decision', lambda: validate_node_decisions(value, candidates, []))

    def test_supports_exact_revision_refs_fp_and_no_global_dag_constraint(self):
        nodes = {uid(n): {'knode_id': uid(n + 10), 'kind': 'proposition'} for n in (1, 2)}
        edge = {'candidate_key': 'e1', 'from_revision_id': uid(1), 'to_revision_id': uid(2),
                'predicate': 'supports', 'qualifiers': {'scope': 'experiment', 'conditions': []},
                'rationale': 'The accepted measurement supports this scoped conclusion.'}
        reverse = {**deepcopy(edge), 'candidate_key': 'e2',
                   'from_revision_id': uid(2), 'to_revision_id': uid(1)}
        response = {'edges': [edge, reverse], 'complete': True}
        self.assertEqual(len(normalize_edges(response, nodes)), 2)
        fp = edge_fingerprints(uid(11), uid(12), 'supports', edge['qualifiers'])
        changed = edge_fingerprints(uid(11), uid(12), 'supports', {'scope': 'narrow', 'conditions': []})
        self.assertEqual(fp['identity_fingerprint'], changed['identity_fingerprint'])
        self.assertNotEqual(fp['content_fingerprint'], changed['content_fingerprint'])
        nodes[uid(3)] = nodes[uid(1)]
        first = normalize_edges({'edges': [edge], 'complete': True}, nodes)[0]
        edge['from_revision_id'] = uid(3)
        second = normalize_edges({'edges': [edge], 'complete': True}, nodes)[0]
        self.assertEqual(first['content_fingerprint'], second['content_fingerprint'])
        edge['to_revision_id'] = uid(1)
        self.error('invalid_edge_proposal', lambda: normalize_edges({'edges': [edge], 'complete': True}, nodes))

    def test_edge_unknown_revision_duplicates_wrong_kind_and_decision_coverage(self):
        nodes = {uid(1): {'knode_id': uid(11), 'kind': 'observation'},
                 uid(2): {'knode_id': uid(12), 'kind': 'proposition'}}
        edge = {'candidate_key': 'e1', 'from_revision_id': uid(1), 'to_revision_id': uid(2),
                'predicate': 'supports', 'qualifiers': {'scope': '', 'conditions': []}, 'rationale': 'Evidence.'}
        response = {'edges': [edge, {**edge, 'candidate_key': 'e2'}], 'complete': True}
        self.error('duplicate_edge_proposal', lambda: normalize_edges(response, nodes))
        response['edges'].pop()
        edge['to_revision_id'] = uid(9)
        self.error('invalid_edge_proposal', lambda: normalize_edges(response, nodes))
        edge['to_revision_id'] = uid(2)
        nodes[uid(2)]['kind'] = 'observation'
        self.error('invalid_edge_proposal', lambda: normalize_edges(response, nodes))
        nodes[uid(2)]['kind'] = 'proposition'
        candidates = normalize_edges(response, nodes)
        decisions = {'complete': True, 'decisions': [{'candidate_key': 'e1', 'verdict': 'accepted',
                      'reason_codes': ['scope_supported'], 'reason': 'The target is scoped to this result.'}]}
        self.assertEqual(validate_edge_decisions(decisions, candidates)['e1']['verdict'], 'accepted')
        decisions['decisions'] = []
        self.error('invalid_edge_decision', lambda: validate_edge_decisions(decisions, candidates))

    def test_output_schemas_are_closed_and_bind_ids(self):
        def check(schema):
            if schema.get('type') == 'object':
                self.assertIs(schema['additionalProperties'], False)
                self.assertEqual(set(schema['required']), set(schema['properties']))
                for child in schema['properties'].values():
                    check(child)
            if schema.get('type') == 'array':
                check(schema['items'])
        for schema in (NODE_SCHEMA([uid(1)], ['a' * 64]), NODE_DECISION_SCHEMA(['a'], []),
                       EDGE_SCHEMA([uid(2)]), EDGE_DECISION_SCHEMA(['e1'])):
            check(schema)
        source = NODE_SCHEMA([uid(1)], [])['properties']['nodes']['items']['properties']['evidence']['items']
        self.assertEqual(source['properties']['information_id']['enum'], [uid(1)])
        self.assertEqual(source['properties']['media_sha256']['enum'], [None])


if __name__ == '__main__':
    unittest.main()
