"""Immutable version lineage versus a moving current-head view; no database writes."""

from copy import deepcopy
import unittest

from palimpsest.version_provenance import annotate, graph_view, load


def version(identifier, series='series', parent=None):
    return {'version_id': identifier, 'series_id': series, 'parent_version_id': parent,
            'data_id': identifier + '-data', 'version_number': 1 if parent is None else 2,
            'title': identifier, 'message': 'Synthetic version fixture', 'actor_ref': 'test',
            'created_at': '2026-09-13T00:00:00Z'}


def state():
    return {'versions': {'v1': version('v1'), 'v2': version('v2', parent='v1')},
            'heads': {'series': 'v1'}, 'by_revision': {
                'revision': [{'record_id': 'origin', 'operation': 'i2k', 'version_ids': ['v1']}]}}


def node():
    return {'knode_id': 'node', 'knode_revision_id': 'revision', 'origin_record_id': 'origin',
            'generation_origin': {'origin_operation': 'i2k', 'is_inferred': False},
            'current_applicability': 'needs_revalidation'}


class VersionProvenanceTests(unittest.TestCase):
    def test_origin_remains_v1_when_a_new_accepted_support_binds_v2(self):
        source, original = state(), node()
        before = deepcopy(original)
        source['by_revision']['revision'].append({'record_id': 'reuse', 'operation': 'k2k', 'version_ids': ['v2']})
        source['heads']['series'] = 'v2'
        annotation = annotate(source, original)
        self.assertEqual([v['version_id'] for v in annotation['origin_data_versions']], ['v1'])
        self.assertEqual([support['record_id'] for support in annotation['data_version_supports']], ['origin', 'reuse'])
        self.assertEqual(annotation['data_version_supports'][1]['versions'], [source['versions']['v2']])
        view = graph_view(source, original)
        self.assertEqual(view, {'source_version_status': 'current',
                               'source_version_current_heads': [{'series_id': 'series', 'version_id': 'v2'}]})
        merged = {**original, **annotation, **view}
        self.assertEqual(merged['generation_origin'], original['generation_origin'])
        self.assertEqual(merged['current_applicability'], 'needs_revalidation')
        self.assertEqual(original, before)
        annotation['origin_data_versions'][0]['title'] = 'Changed caller copy'
        annotation['data_version_supports'][0]['versions'][0]['title'] = 'Changed caller copy'
        self.assertEqual(source['versions']['v1']['title'], 'v1')

    def test_head_movement_changes_graph_only_not_frozen_annotations(self):
        source, original = state(), node()
        frozen = annotate(source, original)
        self.assertEqual(graph_view(source, original)['source_version_status'], 'current')
        source['heads']['series'] = 'v2'
        self.assertEqual(graph_view(source, original)['source_version_status'], 'historical')
        self.assertEqual(annotate(source, original), frozen)
        self.assertNotIn('head_version_id', frozen['origin_data_versions'][0])
        self.assertNotIn('source_version_status', frozen)

    def test_legacy_data_membership_never_backfills_generation_or_support(self):
        source, original = state(), node()
        original['knode_revision_id'] = 'legacy'
        original['source_data_ids'] = [source['versions']['v1']['data_id']]
        self.assertEqual(annotate(source, original), {'origin_data_versions': [], 'data_version_supports': []})
        self.assertEqual(graph_view(source, original), {'source_version_status': 'untracked', 'source_version_current_heads': []})
        self.assertEqual(annotate(None, original), {'origin_data_versions': [], 'data_version_supports': []})
        self.assertEqual(graph_view(None, original)['source_version_status'], 'untracked')

    def test_later_version_support_does_not_relabel_an_unversioned_origin(self):
        source, original = state(), node()
        source['by_revision']['revision'] = [{'record_id': 'reuse', 'operation': 'i2k', 'version_ids': ['v2']}]
        source['heads']['series'] = 'v2'
        self.assertEqual(annotate(source, original)['origin_data_versions'], [])
        self.assertEqual(graph_view(source, original)['source_version_status'], 'current')

    def test_two_versions_of_one_series_in_a_comparison_are_never_fully_current(self):
        source, original = state(), node()
        source['by_revision']['revision'][0]['version_ids'] = ['v1', 'v2']
        for head in ('v1', 'v2', None):
            source['heads']['series'] = head
            self.assertEqual(graph_view(source, original)['source_version_status'], 'historical')
        source['by_revision']['revision'].append({'record_id': 'separate-current-support',
                                                'operation': 'k2k', 'version_ids': ['v2']})
        source['heads']['series'] = 'v2'
        self.assertEqual(graph_view(source, original)['source_version_status'], 'current')

    def test_one_support_must_match_every_series_head(self):
        source, original = state(), node()
        source['versions']['other-v1'] = version('other-v1', 'other-series')
        source['heads']['other-series'] = 'other-v1'
        source['by_revision']['revision'][0]['version_ids'] = ['v1', 'other-v1']
        self.assertEqual(graph_view(source, original)['source_version_status'], 'current')
        source['heads']['series'] = 'v2'
        self.assertEqual(graph_view(source, original)['source_version_status'], 'historical')
        self.assertEqual(len(graph_view(source, original)['source_version_current_heads']), 2)

    def test_bindings_are_for_exact_revision_not_every_revision_of_a_logical_node(self):
        source, original = state(), node()
        original['knode_revision_id'] = 'later-revision-of-same-node'
        self.assertEqual(annotate(source, original)['data_version_supports'], [])
        self.assertEqual(graph_view(source, original)['source_version_status'], 'untracked')

    def test_node_and_edge_with_same_revision_uuid_keep_separate_version_supports(self):
        source, original = state(), node()
        edge = {'kedge_id': 'edge', 'kedge_revision_id': original['knode_revision_id'], 'origin_record_id': 'edge-origin',
                'applicability': 'pending', 'from_knode_revision_id': 'from', 'to_knode_revision_id': 'to'}
        before = deepcopy(edge)
        source['by_edge_revision'] = {'revision': [
            {'record_id': 'edge-origin', 'operation': 'n2e', 'version_ids': ['v2']}]}
        source['heads']['series'] = 'v2'
        self.assertEqual([v['version_id'] for v in annotate(source, original)['origin_data_versions']], ['v1'])
        self.assertEqual([v['version_id'] for v in annotate(source, edge)['origin_data_versions']], ['v2'])
        self.assertEqual(annotate(source, edge)['data_version_supports'][0]['operation'], 'n2e')
        self.assertEqual(graph_view(source, original)['source_version_status'], 'historical')
        self.assertEqual(graph_view(source, edge)['source_version_status'], 'current')
        self.assertEqual({**edge, **annotate(source, edge), **graph_view(source, edge)}['applicability'], 'pending')
        self.assertEqual(edge, before)
        with self.assertRaisesRegex(ValueError, 'exact_typed_knowledge_revision_required'):
            annotate(source, {**original, 'kedge_revision_id': 'revision'})

    def test_edge_origin_is_immutable_when_a_later_n2e_support_tracks_the_new_head(self):
        source = state()
        edge = {'kedge_id': 'edge', 'kedge_revision_id': 'edge-revision', 'origin_record_id': 'edge-origin'}
        source['by_edge_revision'] = {'edge-revision': [
            {'record_id': 'edge-origin', 'operation': 'n2e', 'version_ids': ['v1']},
            {'record_id': 'edge-reuse', 'operation': 'n2e', 'version_ids': ['v2']}]}
        frozen = annotate(source, edge)
        source['heads']['series'] = 'v2'
        self.assertEqual(graph_view(source, edge)['source_version_status'], 'current')
        self.assertEqual(annotate(source, edge), frozen)
        self.assertEqual([v['version_id'] for v in frozen['origin_data_versions']], ['v1'])
        self.assertEqual(annotate(None, edge)['origin_data_versions'], [])

    def test_optional_schema_and_loaded_explicit_bindings(self):
        class Rows:
            def __init__(self, values): self.values = values
            def fetchone(self): return self.values[0]
            def fetchall(self): return self.values
        class Connection:
            def __init__(self, results): self.results = iter(results); self.calls = []
            def execute(self, sql): self.calls.append(sql); return Rows(next(self.results))
        absent = Connection([[{'relation': None}]])
        self.assertIsNone(load(absent))
        self.assertEqual(len(absent.calls), 1)
        conn = Connection([[{'relation': 'canonical_store.data_versions'}], [version('v1'), version('v2', parent='v1')],
            [{'series_id': 'series', 'head_version_id': 'v2'}],
            [{'record_id': 'origin', 'result_node_revision_id': 'revision', 'operation': 'i2k', 'version_id': 'v1'},
             {'record_id': 'reuse', 'result_node_revision_id': 'revision', 'operation': 'k2k', 'version_id': 'v1'},
             {'record_id': 'reuse', 'result_node_revision_id': 'revision', 'operation': 'k2k', 'version_id': 'v2'},
             {'record_id': 'edge-origin', 'result_node_revision_id': None, 'result_edge_revision_id': 'revision',
              'operation': 'n2e', 'version_id': 'v2'}]])
        loaded = load(conn)
        self.assertEqual(loaded['by_revision']['revision'][1]['version_ids'], ['v1', 'v2'])
        self.assertEqual(annotate(loaded, node())['origin_data_versions'], [version('v1')])
        self.assertEqual(graph_view(loaded, node())['source_version_status'], 'historical')
        edge = {'kedge_revision_id': 'revision', 'origin_record_id': 'edge-origin'}
        self.assertEqual(annotate(loaded, edge)['origin_data_versions'], [version('v2', parent='v1')])
        self.assertEqual(graph_view(loaded, edge)['source_version_status'], 'current')


if __name__ == '__main__':
    unittest.main()
