"""Prepare deterministic BGE-M3 candidate pairs for typed N2E review."""

import argparse
from hashlib import sha256
import heapq
import json
import math
from pathlib import Path


PROFILE = 'bge-m3-semantic-neighbors-v1'


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return sha256(_json(value).encode()).hexdigest()


def embedding_request(packet):
    nodes = packet.get('nodes') if isinstance(packet, dict) else None
    if packet.get('schema_version') != 'n2e-input-v1' or not isinstance(nodes, list) or not nodes:
        raise ValueError('invalid_n2e_input')
    documents, seen = [], set()
    for node in nodes:
        revision_id = node.get('knode_revision_id')
        if (not isinstance(revision_id, str) or revision_id in seen
                or node.get('kind') not in ('proposition', 'observation')
                or not isinstance(node.get('statement'), str)
                or not isinstance(node.get('semantic_payload'), dict)):
            raise ValueError('invalid_n2e_input')
        seen.add(revision_id)
        text = '\n'.join((node['kind'], node['statement'], _json(node['semantic_payload'])))
        documents.append({'document_id': revision_id, 'text': text})
    return {'documents': documents, 'schema_version': 'wiki-embedding-request-v1'}


def _document_vectors(request, result):
    rows = result.get('documents') if isinstance(result, dict) else None
    if (result.get('schema_version') != 'wiki-embedding-result-v1'
            or result.get('input_sha256') != _digest(request)
            or not isinstance(rows, list) or len(rows) != len(request['documents'])):
        raise ValueError('invalid_embedding_result')
    vectors = {}
    for source, row in zip(request['documents'], rows, strict=True):
        chunks = row.get('chunks') if isinstance(row, dict) else None
        if row.get('document_id') != source['document_id'] or not isinstance(chunks, list) or not chunks:
            raise ValueError('invalid_embedding_result')
        dense = [chunk.get('dense') for chunk in chunks]
        dimensions = len(dense[0]) if isinstance(dense[0], list) else 0
        if not dimensions or any(not isinstance(v, list) or len(v) != dimensions for v in dense):
            raise ValueError('invalid_embedding_result')
        mean = [math.fsum(v[index] for v in dense) / len(dense) for index in range(dimensions)]
        norm = math.sqrt(math.fsum(value * value for value in mean))
        if not norm or not math.isfinite(norm):
            raise ValueError('invalid_embedding_result')
        vectors[source['document_id']] = tuple(value / norm for value in mean)
    return vectors


def select_pairs(request, result, *, top_neighbors=3, minimum_score=0.75):
    if type(top_neighbors) is not int or top_neighbors < 1 or not -1 <= minimum_score <= 1:
        raise ValueError('invalid_selection_policy')
    vectors = _document_vectors(request, result)
    identifiers = sorted(vectors)
    neighbors = {identifier: [] for identifier in identifiers}
    scores = {}
    for index, source in enumerate(identifiers):
        for target in identifiers[index + 1:]:
            score = math.sumprod(vectors[source], vectors[target])
            if score < minimum_score:
                continue
            key = (source, target)
            scores[key] = score
            heapq.heappush(neighbors[source], (score, target))
            heapq.heappush(neighbors[target], (score, source))
    selected = set()
    for source, choices in neighbors.items():
        for score, target in heapq.nlargest(top_neighbors, choices, key=lambda item: (item[0], item[1])):
            selected.add(tuple(sorted((source, target))))
    return [{'from_revision_id': source, 'to_revision_id': target,
             'dense_score': round(scores[(source, target)], 8)}
            for source, target in sorted(selected)]


def make_batches(packet, pairs, *, max_nodes=64, max_pairs=None):
    if (type(max_nodes) is not int or max_nodes < 2
            or max_pairs is not None and (type(max_pairs) is not int or max_pairs < 1)):
        raise ValueError('invalid_selection_policy')
    nodes = {node['knode_revision_id']: node for node in packet['nodes']}
    batches, current_pairs, current_ids = [], [], set()
    for pair in pairs:
        pair_ids = {pair['from_revision_id'], pair['to_revision_id']}
        if not pair_ids <= nodes.keys():
            raise ValueError('invalid_selection_pair')
        if current_pairs and (len(current_ids | pair_ids) > max_nodes
                              or max_pairs is not None and len(current_pairs) >= max_pairs):
            batches.append((current_ids, current_pairs))
            current_pairs, current_ids = [], set()
        current_pairs.append(pair)
        current_ids.update(pair_ids)
    if current_pairs:
        batches.append((current_ids, current_pairs))
    return [([nodes[identifier] for identifier in sorted(identifiers)], batch_pairs)
            for identifiers, batch_pairs in batches]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json(value), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--embedding-result', type=Path)
    parser.add_argument('--output-directory', type=Path)
    parser.add_argument('--top-neighbors', type=int, default=3)
    parser.add_argument('--minimum-score', type=float, default=0.75)
    parser.add_argument('--max-nodes', type=int, default=64)
    parser.add_argument('--max-pairs', type=int)
    args = parser.parse_args()
    packet = json.loads(args.input.read_text(encoding='utf-8'))
    request = embedding_request(packet)
    if not args.request.exists():
        write_json(args.request, request)
    elif json.loads(args.request.read_text(encoding='utf-8')) != request:
        raise SystemExit('existing embedding request does not match input')
    if args.embedding_result is None:
        print(_json({'documents': len(request['documents']), 'request_sha256': _digest(request)}))
        return
    if args.output_directory is None:
        parser.error('--output-directory is required with --embedding-result')
    result = json.loads(args.embedding_result.read_text(encoding='utf-8'))
    pairs = select_pairs(request, result, top_neighbors=args.top_neighbors,
                         minimum_score=args.minimum_score)
    batches = make_batches(packet, pairs, max_nodes=args.max_nodes, max_pairs=args.max_pairs)
    result_sha = sha256(args.embedding_result.read_bytes()).hexdigest()
    profile_sha = _digest(result['profile'])
    manifest_batches = []
    for ordinal, (nodes, batch_pairs) in enumerate(batches, 1):
        value = {'nodes': nodes, 'schema_version': 'n2e-input-v1',
                 'semantic_discovery': {'schema_version': PROFILE,
                     'embedding_profile_sha256': profile_sha,
                     'embedding_result_sha256': result_sha, 'pairs': batch_pairs}}
        relative = f'batches/{ordinal:04d}/input.json'
        write_json(args.output_directory / relative, value)
        manifest_batches.append({'batch': ordinal, 'node_count': len(nodes),
            'pair_count': len(batch_pairs), 'input_sha256': _digest(value), 'input_file': relative})
    manifest = {'schema_version': 'semantic-n2e-selection-v1',
        'source_node_count': len(packet['nodes']), 'candidate_pair_count': len(pairs),
        'policy': {'top_neighbors_per_node': args.top_neighbors,
            'include_dense_score_at_least': args.minimum_score,
            'document_vector': 'normalized_mean_chunk_dense', 'max_nodes_per_batch': args.max_nodes,
            'max_pairs_per_batch': args.max_pairs},
        'embedding_request_sha256': _digest(request), 'embedding_result_sha256': result_sha,
        'embedding_profile_sha256': profile_sha, 'batches': manifest_batches}
    write_json(args.output_directory / 'selection-manifest.json', manifest)
    print(_json({'batches': len(batches), 'candidate_pairs': len(pairs),
                 'source_nodes': len(packet['nodes'])}))


if __name__ == '__main__':
    main()
