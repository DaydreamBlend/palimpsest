import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    'prepare_n2e_semantic_batches',
    Path(__file__).resolve().parents[2] / 'tools' / 'prepare_n2e_semantic_batches.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SemanticN2eBatchTests(unittest.TestCase):
    def test_pairs_are_unordered_unique_and_bounded(self):
        nodes = [{'knode_revision_id': value, 'kind': 'proposition', 'statement': value,
                  'semantic_payload': {'subject': value}} for value in ('a', 'b', 'c')]
        packet = {'schema_version': 'n2e-input-v1', 'nodes': nodes}
        request = MODULE.embedding_request(packet)
        documents = []
        for identifier, vector in [('a', [1.0, 0.0]), ('b', [0.9, 0.435889894]), ('c', [0.0, 1.0])]:
            documents.append({'document_id': identifier, 'chunks': [{'dense': vector}]})
        result = {'schema_version': 'wiki-embedding-result-v1',
                  'input_sha256': MODULE._digest(request), 'documents': documents}
        pairs = MODULE.select_pairs(request, result, top_neighbors=1, minimum_score=0.5)
        self.assertEqual([('a', 'b')], [(p['from_revision_id'], p['to_revision_id']) for p in pairs])
        batches = MODULE.make_batches(packet, pairs, max_nodes=2, max_pairs=1)
        self.assertEqual(1, len(batches))
        self.assertEqual({'a', 'b'}, {node['knode_revision_id'] for node in batches[0][0]})


if __name__ == '__main__':
    unittest.main()
