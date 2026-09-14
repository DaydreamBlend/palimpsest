"""Standalone D2K consumer contracts; synthetic views, no DB/model/authority calls."""

from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import MagicMock, patch

from palimpsest import d2k, knowledge_provenance
from palimpsest.desktop_read import DesktopReadService
from palimpsest.errors import PalimpsestError
from palimpsest.i2k import digest
from palimpsest.wiki_archive import PROFILE, validate_archive_files
from palimpsest.wiki_query import (generation_schema, normalize_answer, validation_prompt,
    validate_answer, render_answer, ANSWER_WITH_DATA_SCHEMA)
from palimpsest.wiki_retrieval import WikiRetrieval, knowledge_projection
from test_d2k import text_packet, pdf_view, uid
from test_wiki_query import context
from test_wiki_query_inference import inference_context, decision


def data_fixture(*, pdf=False):
    if pdf:
        raw = b'%PDF-1.7\nSynthetic immutable original, no real renderer execution.'
        image = b'Synthetic pixel descriptor only; not an actual renderer result.'
        view = pdf_view()
        view.update(data_id=sha256(raw).hexdigest(), original_byte_size=len(raw))
        packet = d2k.build_input(view['data_id'], media_type='application/pdf', original_byte_size=len(raw), views=[view])
        citation = {'view_id': view['view_id'], 'source_role': 'results'}
    else:
        packet = text_packet()
        view = packet['views'][0]
        raw, image = view['text'].encode('utf-8'), None
        citation = {'view_id': view['view_id'], 'char_start': 1, 'char_end': 23, 'source_role': 'results'}
    evidence = d2k.normalize_evidence(citation, packet)
    row = {'grounding_id': uid(30), 'node_revision_id': uid(11), 'origin_record_id': uid(10011),
           'data_id': packet['data_id'], 'view_id': view['view_id'], 'evidence': evidence}
    node = {'knode_id': uid(20011), 'knode_revision_id': uid(11), 'current_revision_id': uid(11),
        'origin_record_id': uid(10011), 'kind': 'proposition', 'statement': 'A synthetic explicitly reported source statement.',
        'identity_scope': 'general', 'record_disposition': 'accepted_new',
        'current_applicability': 'current_premises', 'source_version_status': 'untracked', 'data_version_supports': [],
        'generation_origin': {'origin_operation': 'd2k', 'is_inferred': False, 'origin_record_id': uid(10011)}}
    record = {'record_id': uid(10011), 'record_type': 'd2k', 'result_node_revision_id': uid(11),
              'information_ids': [], 'data_grounding_ids': [uid(30)]}
    source = {'data_id': packet['data_id'], 'byte_size': len(raw), 'media_type': packet['media_type'],
              'source_version_status': 'untracked'}
    return {'packet': packet, 'view': view, 'raw': raw, 'image': image, 'row': row,
            'node': node, 'record': record, 'source': source}


def data_context(*, pdf=False):
    fixture = data_fixture(pdf=pdf)
    ctx = context('knowledge')
    ctx.update(information=[], sources=[], knowledge=[], inference_citations_supported=True,
               data_citations_supported=True, source_version_snapshot={'versions': [], 'heads': {}},
               data_sources=[fixture['source']], data_views=[fixture['view']])
    graph = {'nodes': [fixture['node']], 'groundings': [], 'data_groundings': [fixture['row']]}
    _, ctx['knowledge'] = knowledge_projection(graph, {}, [fixture['record']], None, set(),
        data_sources=ctx['data_sources'], data_views=ctx['data_views'])
    return ctx, fixture


def proposal(grounding_id=uid(30)):
    return {'status': 'answered', 'claims': [{'claim_key': 'source', 'text': '원문에 명시된 합성 시험 주장이다.',
        'evidence': [], 'source_evidence': [], 'knowledge_evidence': [], 'data_evidence': [{'grounding_id': grounding_id}]}],
        'search_query': None, 'source_requests': [], 'unresolved': []}


def mixed_context():
    ctx, value = inference_context(), data_fixture()
    source, other, inferred = ctx['knowledge']
    row = deepcopy(value['row'])
    row.update(node_revision_id=source['knode_revision_id'], origin_record_id=source['origin_record_id'])
    direct = knowledge_provenance.data_grounding(row)
    source.update(generation_origin={'origin_operation': 'd2k', 'is_inferred': False,
                                     'origin_record_id': source['origin_record_id']},
        groundings=[], direct_groundings=[], direct_data_groundings=[direct], transitive_data_refs=[])
    source_record = {**source['retrieval_support']['records'][0], 'operation': 'd2k',
                     'information_ids': [], 'data_grounding_ids': [row['grounding_id']]}
    source['retrieval_support'].update(operation='d2k', information_ids=[], source_data_ids=[row['data_id']], records=[source_record])
    ctx['information'] = ctx['information'][1:]
    inferred['transitive_source_refs'] = deepcopy(other['groundings'])
    inferred.update(direct_data_groundings=[], transitive_data_refs=[direct])
    inferred['retrieval_support']['records'][0] = source_record
    inferred['retrieval_support']['information_ids'] = [ctx['information'][0]['information_id']]
    inferred['retrieval_support']['source_data_ids'] = sorted([row['data_id'], ctx['information'][0]['data_id']])
    ctx.update(data_citations_supported=True, data_sources=[value['source']], data_views=[value['view']])
    return ctx, value


class D2KConsumerTests(unittest.TestCase):
    def test_generic_metadata_hashes_only_new_d_quotes_without_changing_legacy_or_origin(self):
        value = data_fixture()
        source = {**value['node'], 'direct_data_groundings': [knowledge_provenance.data_grounding(value['row'])],
                  'transitive_data_refs': [{'evidence': {'quote': 'Another original quote'}}],
                  'groundings': [{'quote': 'Legacy I quote'}]}
        before = deepcopy(source)
        projected = knowledge_provenance.data_reference_metadata(source)
        self.assertEqual(source, before)
        self.assertNotIn('quote', projected['direct_data_groundings'][0])
        self.assertEqual(projected['direct_data_groundings'][0]['quote_sha256'], value['row']['evidence']['quote_sha256'])
        self.assertNotIn('quote', projected['transitive_data_refs'][0]['evidence'])
        self.assertEqual(projected['groundings'], source['groundings'])
        self.assertEqual(projected['generation_origin'], source['generation_origin'])
        legacy = {'groundings': [{'quote': 'Legacy exact I quote'}], 'statement': 'Existing statement'}
        self.assertEqual(json.dumps(knowledge_provenance.data_reference_metadata(legacy)), json.dumps(legacy))
        from palimpsest import k2k
        from palimpsest.knowledge_requests import generation_request
        from test_paper_wiki import source_packet
        k2k_prompt_input = k2k._prompt_snapshot({'input': {'nodes': [source]}, 'existing_nodes': []})
        self.assertNotIn(value['row']['evidence']['quote'], json.dumps(k2k_prompt_input))
        self.assertNotIn('Another original quote', json.dumps(k2k_prompt_input))
        snapshot = {'input': source_packet(), 'existing_nodes': [source], 'existing_edges': []}
        prompt, _ = generation_request(snapshot, [])
        self.assertNotIn(value['row']['evidence']['quote'], prompt)
        self.assertNotIn('Another original quote', prompt)
        self.assertEqual(source, before)

    def test_mixed_i2k_and_d2k_inference_keeps_both_complete_typed_leaf_routes(self):
        ctx, value = mixed_context()
        response = proposal()
        response['claims'][0].update(data_evidence=[], knowledge_evidence=[{
            'node_revision_id': ctx['knowledge'][-1]['knode_revision_id']}])
        answer = normalize_answer(response, ctx)
        citation = answer['claims'][0]['knowledge_evidence'][0]
        self.assertEqual(answer['claims'][0]['epistemic_basis'], 'accepted_system_inference')
        self.assertEqual(citation['direct_groundings'], [])
        self.assertEqual(citation['direct_data_groundings'], [])
        self.assertEqual(len(citation['transitive_source_refs']), 1)
        self.assertEqual(len(citation['transitive_data_refs']), 1)
        self.assertEqual(citation['transitive_data_refs'][0]['data_id'], value['packet']['data_id'])
        self.assertEqual({row['operation'] for row in citation['retrieval_support']['records']}, {'i2k', 'd2k', 'k2k'})
        self.assertIn('D2K 근거', render_answer(answer, validate_answer(decision(answer), answer)))
        for missing in ('data_leaf', 'i_leaf'):
            changed = deepcopy(ctx)
            if missing == 'data_leaf': changed['data_views'] = []
            else: changed['information'] = []
            with self.subTest(missing=missing), self.assertRaises(PalimpsestError):
                normalize_answer(response, changed)

    def test_origin_and_stale_premise_remain_separate_from_later_d2k_support(self):
        ctx, _ = mixed_context()
        source, other, inferred = ctx['knowledge']
        derivation = {**deepcopy(inferred['derivations'][0]), 'derivation_depth': 1}
        state = {'revisions': {node['knode_revision_id']: {key: node[key] for key in (
            'knode_revision_id', 'knode_id', 'origin_record_id', 'current_revision_id')} for node in ctx['knowledge']},
            'by_record': {derivation['record_id']: derivation}, 'by_result': {inferred['knode_revision_id']: [derivation]},
            'edges': {inferred['knode_revision_id']: derivation['premise_revision_ids']},
            'groundings': {other['knode_revision_id']: other['groundings']},
            'data_groundings': {source['knode_revision_id']: source['direct_data_groundings']}}
        initial = knowledge_provenance.describe(state, source['knode_revision_id'])
        self.assertEqual(initial['generation_origin']['origin_operation'], 'd2k')
        self.assertFalse(initial['generation_origin']['is_inferred'])
        self.assertEqual(initial['direct_groundings'], [])
        before = knowledge_provenance.describe(state, inferred['knode_revision_id'])
        self.assertEqual(len(before['transitive_data_refs']), 1)
        state['revisions'][source['knode_revision_id']]['current_revision_id'] = uid(999)
        extra = {**deepcopy(source['direct_data_groundings'][0]), 'node_revision_id': inferred['knode_revision_id'],
                 'grounding_id': uid(900), 'origin_record_id': uid(901)}
        state['data_groundings'][inferred['knode_revision_id']] = [extra]
        current = knowledge_provenance.describe(state, inferred['knode_revision_id'])
        self.assertEqual(current['generation_origin'], before['generation_origin'])
        self.assertTrue(current['generation_origin']['is_inferred'])
        self.assertEqual(current['current_applicability'], 'needs_revalidation')
        self.assertEqual(current['stale_premise_revision_ids'], [source['knode_revision_id']])

    def test_exact_text_grounding_rebuilds_original_coordinates_and_never_adds_i(self):
        value = data_fixture()
        before = deepcopy(value)
        grounding, view = knowledge_provenance.verify_data_grounding(value['row'], value['view'], value['raw'])
        self.assertEqual(value, before)
        self.assertNotIn('information_id', grounding)
        self.assertNotIn('source_execution_id', grounding)
        self.assertEqual(grounding['grounding_type'], 'data')
        self.assertEqual(grounding['quote'], value['raw'][grounding['locator']['byte_start']:grounding['locator']['byte_end']].decode())
        self.assertEqual(view, value['view'])
        for mutation in ('original', 'quote', 'view', 'owner'):
            changed = deepcopy(value)
            if mutation == 'original': changed['raw'] += b'changed'
            elif mutation == 'quote': changed['row']['evidence']['quote'] += 'changed'
            elif mutation == 'owner': changed['row']['data_id'] = 'f' * 64
            else: changed['view']['locator']['byte_start'] += 1
            with self.subTest(mutation=mutation), self.assertRaises(PalimpsestError):
                knowledge_provenance.verify_data_grounding(changed['row'], changed['view'], changed['raw'])

    def test_pdf_retained_asset_is_verified_without_claiming_native_pdf_delivery_or_new_render(self):
        value = data_fixture(pdf=True)
        grounding, _ = knowledge_provenance.verify_data_grounding(value['row'], value['view'], value['raw'], image=value['image'])
        self.assertEqual(grounding['representation'], 'original_pdf_page_image')
        self.assertEqual(grounding['quote'], '')
        self.assertEqual(grounding['media_sha256'], value['view']['image_sha256'])
        self.assertNotIn('original_pdf_delivered', grounding)
        with self.assertRaises(PalimpsestError):
            knowledge_provenance.verify_data_grounding(value['row'], value['view'], value['raw'], image=b'different')

    def test_i_free_d2k_route_uses_explicit_data_membership_and_all_record_groundings(self):
        value = data_fixture()
        graph = {'nodes': [value['node']], 'groundings': [], 'data_groundings': [value['row']]}
        self.assertEqual(knowledge_projection(graph, {}, [value['record']], None, set()), ([], []))
        docs, nodes = knowledge_projection(graph, {}, [value['record']], None, set(),
            data_sources=[value['source']], data_views=[value['view']])
        self.assertEqual(len(nodes), 1)
        self.assertEqual(docs[0]['information_ids'], [])
        self.assertEqual(nodes[0]['generation_origin']['origin_operation'], 'd2k')
        self.assertEqual(nodes[0]['retrieval_basis'], 'source_content')
        self.assertEqual(nodes[0]['direct_groundings'], [])
        self.assertEqual(nodes[0]['retrieval_support']['source_data_ids'], [value['source']['data_id']])
        broken = {**value['record'], 'data_grounding_ids': [uid(30), uid(99)]}
        self.assertEqual(knowledge_projection(graph, {}, [broken], None, set(),
            data_sources=[value['source']], data_views=[value['view']]), ([], []))
        wrong_operation = {**value['record'], 'record_type': 'i2k'}
        self.assertEqual(knowledge_projection(graph, {}, [wrong_operation], None, set(),
            data_sources=[value['source']], data_views=[value['view']]), ([], []))

    def test_current_d2k_support_after_same_data_revert_keeps_original_generation_context(self):
        value = data_fixture()
        owner, series = value['packet']['data_id'], uid(500)
        old = {'version_id': uid(501), 'series_id': series, 'data_id': owner}
        current = {'version_id': uid(502), 'series_id': series, 'data_id': owner}
        binding = {'record_id': value['record']['record_id'], 'operation': 'd2k',
                   'version_ids': [old['version_id']], 'versions': [old]}
        value['node']['data_version_supports'] = [binding]
        versions = {'versions': {old['version_id']: old, current['version_id']: current},
                    'heads': {series: current['version_id']},
                    'by_revision': {value['node']['knode_revision_id']: [{key: binding[key] for key in ('record_id', 'operation', 'version_ids')}]}}
        graph = {'nodes': [value['node']], 'groundings': [], 'data_groundings': [value['row']]}
        args = {'data_sources': [value['source']], 'data_views': [value['view']]}
        self.assertEqual(knowledge_projection(graph, {}, [value['record']], versions, set(), **args), ([], []))
        before_origin = deepcopy(value['node']['generation_origin'])
        reuse = {**value['record'], 'record_id': uid(10012), 'data_grounding_ids': [uid(31)]}
        graph['data_groundings'].append({**value['row'], 'grounding_id': uid(31), 'origin_record_id': reuse['record_id']})
        support = {'record_id': reuse['record_id'], 'operation': 'd2k', 'version_ids': [current['version_id']], 'versions': [current]}
        value['node']['data_version_supports'].append(support)
        versions['by_revision'][value['node']['knode_revision_id']].append({key: support[key] for key in ('record_id', 'operation', 'version_ids')})
        _, nodes = knowledge_projection(graph, {}, [value['record'], reuse], versions, set(), **args)
        self.assertEqual(nodes[0]['retrieval_support']['record_id'], reuse['record_id'])
        self.assertEqual(nodes[0]['source_version_status'], 'current')
        self.assertEqual(nodes[0]['generation_origin'], before_origin)
        self.assertEqual(value['node']['data_version_supports'][0], binding)

    def test_old_source_only_v1_v2_and_new_d2k_source_v3_have_distinct_citations(self):
        ctx, value = data_context()
        before = deepcopy(ctx)
        schema = generation_schema(ctx)
        self.assertEqual(schema['properties']['claims']['items']['properties']['data_evidence']['items']['properties']['grounding_id']['enum'], [uid(30)])
        self.assertEqual(schema['properties']['claims']['items']['properties']['knowledge_evidence']['maxItems'], 0)
        answer = normalize_answer(proposal(), ctx)
        self.assertEqual(answer['schema_version'], ANSWER_WITH_DATA_SCHEMA)
        claim = answer['claims'][0]
        self.assertEqual(claim['epistemic_basis'], 'direct_source')
        self.assertEqual(claim['evidence'], [])
        self.assertEqual(claim['knowledge_evidence'], [])
        self.assertEqual(claim['data_evidence'][0]['quote'], value['row']['evidence']['quote'])
        validated = validate_answer(decision(answer), answer)
        rendered = render_answer(answer, validated)
        self.assertIn('D2K 직접 원문 근거', rendered)
        self.assertIn(value['packet']['data_id'], rendered)
        self.assertNotIn('K2K 추론', rendered)
        self.assertIn('data_views', validation_prompt(ctx, answer))
        self.assertEqual(ctx, before)
        self.assertNotIn('data_evidence', generation_schema(context())['properties']['claims']['items']['properties'])
        self.assertNotIn('data_evidence', generation_schema(inference_context())['properties']['claims']['items']['properties'])

    def test_query_rejects_unprovided_views_wrong_data_or_operation_and_forged_quote(self):
        for mutation in ('view', 'owner', 'quote', 'operation', 'disabled', 'historical', 'current_revision'):
            ctx, _ = data_context()
            if mutation == 'view': ctx['data_views'] = []
            elif mutation == 'owner': ctx['data_sources'][0]['data_id'] = 'f' * 64
            elif mutation == 'quote': ctx['knowledge'][0]['direct_data_groundings'][0]['quote'] = 'forged'
            elif mutation == 'operation': ctx['knowledge'][0]['retrieval_support']['records'][0]['operation'] = 'i2k'
            elif mutation == 'disabled': ctx['data_citations_supported'] = False
            elif mutation == 'historical': ctx['data_sources'][0]['source_version_status'] = 'historical'
            else: ctx['knowledge'][0]['current_revision_id'] = uid(999)
            with self.subTest(mutation=mutation), self.assertRaises(PalimpsestError):
                normalize_answer(proposal(), ctx)
        ctx, _ = data_context()
        with self.assertRaises(PalimpsestError): normalize_answer(proposal(uid(999)), ctx)
        duplicate = proposal()
        duplicate['claims'][0]['data_evidence'] *= 2
        with self.assertRaises(PalimpsestError): normalize_answer(duplicate, ctx)

    def test_pdf_query_keeps_image_representation_without_text_quote_or_i(self):
        ctx, value = data_context(pdf=True)
        answer = normalize_answer(proposal(), ctx)
        citation = answer['claims'][0]['data_evidence'][0]
        self.assertEqual((citation['quote'], citation['char_start'], citation['char_end']), ('', 0, 0))
        self.assertNotIn('information_id', citation)
        self.assertEqual(citation['media_sha256'], value['view']['image_sha256'])
        rendered = render_answer(answer, validate_answer(decision(answer), answer))
        self.assertIn('원본 PDF 페이지 1', rendered)

    def test_empty_wiki_archive_accepts_no_i_or_compilation_and_needs_no_membership_schema(self):
        catalog = {'schema_version': PROFILE, 'version': 0, 'papers': {}, 'topics': {}, 'commits': {}}
        raw = json.dumps(catalog).encode()
        archive = validate_archive_files({'catalog.json': raw, f'catalogs/{digest(catalog)}.json': raw})
        self.assertEqual(archive['source_packets'], {})
        self.assertEqual(archive['snapshots'], {})
        self.assertEqual(archive['jobs'], {})

    def test_index_revalidation_keeps_the_explicit_data_selection(self):
        retrieval = WikiRetrieval.__new__(WikiRetrieval)
        corpus = {'wiki_id': uid(1), 'include_data_ids': ['a' * 64]}
        retrieval.corpus = MagicMock(return_value={'changed': True})
        with self.assertRaises(PalimpsestError): retrieval.install(uid(2), corpus, {})
        retrieval.corpus.assert_called_once_with(uid(1), include_data_ids=['a' * 64])

    def test_cli_forwards_only_explicit_data_ids_without_changing_the_legacy_default(self):
        from palimpsest.cli import _parser, _wiki_query
        args = ['wiki', 'retrieval-prepare', '--directory', '/unused/query', '--wiki-id', uid(1), '--index-id', uid(2)]
        self.assertIsNone(_parser().parse_args(args).include_data_id)
        selected = _parser().parse_args(args + ['--include-data-id', 'a' * 64, '--include-data-id', 'b' * 64])
        with patch('palimpsest.wiki_query_runtime.WikiQueryRuntime') as runtime:
            _wiki_query(selected, SimpleNamespace(database_dsn='postgresql://unused', artifact_root='/unused/artifacts'))
        runtime.return_value.prepare_index.assert_called_once_with(uid(1), uid(2), include_data_ids=['a' * 64, 'b' * 64])

    def test_desktop_d2k_reader_needs_owned_grounding_and_never_calls_information(self):
        value = data_fixture()
        service = DesktopReadService.__new__(DesktopReadService)
        service.dsn = 'unused'
        service._knowledge_scope = lambda: ([], [value['packet']['data_id']])
        metadata = {'data_id': value['packet']['data_id'], 'byte_size': len(value['raw']), 'media_type': 'text/plain'}
        store = SimpleNamespace(read=MagicMock(return_value=value['raw']))
        service.database = SimpleNamespace(source=SimpleNamespace(store=store, data=SimpleNamespace(get_data=lambda _: metadata),
            derived=SimpleNamespace(read=MagicMock(side_effect=AssertionError('No image expected'))),
            prepare_input=MagicMock(side_effect=AssertionError('No I/D2I allowed'))))
        conn = MagicMock()
        def execute(sql, params=None):
            result = MagicMock()
            result.fetchone.return_value = ({'relation': 'knowledge_data_groundings'} if 'to_regclass' in sql else
                {**value['row'], 'view': value['view'], 'preparation_id': uid(88)})
            return result
        conn.execute.side_effect = execute
        conn.__enter__.return_value = conn
        with patch('palimpsest.desktop_read.connection', return_value=conn), patch.object(service, '_allowed_knowledge', return_value=True):
            result = service.data_grounding(uid(30))
        self.assertIsNone(result['source_info'])
        self.assertEqual(result['media_kind'], 'text')
        self.assertEqual(result['grounding']['quote'], value['row']['evidence']['quote'])
        self.assertEqual(result['preparation_id'], uid(88))
        self.assertTrue(result['read_only'])
        store.read.reset_mock()
        with patch('palimpsest.desktop_read.connection', return_value=conn), patch.object(service, '_allowed_knowledge', return_value=False), self.assertRaises(PalimpsestError):
            service.data_grounding(uid(30))
        store.read.assert_not_called()


@unittest.skipUnless(sys.platform == 'linux', 'Requires Linux projection filesystem; never PostgreSQL')
class D2KQueryDeliveryTests(unittest.TestCase):
    def test_actual_request_files_require_data_view_delivery_and_replay_without_new_source_calls(self):
        import test_wiki_query_runtime as runtime_fixtures
        from palimpsest.wiki_retrieval import projection_profile
        helper = runtime_fixtures.WikiQueryRuntimeTests('runTest')
        helper.setUp()
        self.addCleanup(helper.doCleanups)
        runtime = helper.runtime
        ctx, value = data_context()
        runtime.retrieval.value['corpus'] = {**ctx, 'source_packets': [], 'projection_profile': projection_profile(),
            'documents': [{'document_id': 'k/' + uid(11), 'kind': 'knowledge', 'knode_revision_id': uid(11),
                           'text': ctx['knowledge'][0]['statement'], 'information_ids': []}]}
        helper.prepare()
        helper.run_search()
        job = runtime.show(helper.identifier)
        retained = runtime._context(job)
        self.assertEqual(retained['information'], [])
        self.assertEqual(retained['data_views'], [value['view']])
        generated = runtime_fixtures.exchange(runtime, helper.identifier, 'generator', proposal())
        generated['receipt']['delivered_knowledge_revision_ids'] = [uid(11)]
        with self.assertRaises(PalimpsestError) as missing:
            runtime.stage(helper.identifier, generated)
        self.assertEqual(missing.exception.code, 'wiki_query_data_delivery_mismatch')
        generated['receipt']['delivered_data_view_ids'] = [value['view']['view_id']]
        staged = runtime.stage(helper.identifier, generated)
        answer = runtime.store.read_json(staged['last_proposal_path'])
        validated = runtime_fixtures.exchange(runtime, helper.identifier, 'validator', decision(answer))
        validated['receipt'].update(delivered_knowledge_revision_ids=[uid(11)],
                                   delivered_data_view_ids=[value['view']['view_id']])
        result = runtime.decide(helper.identifier, validated)
        self.assertEqual(result['state'], 'answered')
        self.assertEqual(result['canonical_writes'], 0)
        self.assertEqual(result['d2i_calls'], 0)
        self.assertEqual(runtime.original_reads, [])
        self.assertEqual(runtime.media_reads, [])
        self.assertEqual(runtime.decide(helper.identifier, validated)['answer_path'], result['answer_path'])


if __name__ == '__main__':
    unittest.main()
