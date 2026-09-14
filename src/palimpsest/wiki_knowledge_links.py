"""Find shared source evidence, never semantic support, without I/O or models."""

from collections import defaultdict
from copy import deepcopy
from hashlib import sha256

from .data import data_id, request_id
from .errors import PalimpsestError
from .i2k import digest


def _fail():
    raise PalimpsestError('invalid_wiki_knowledge_links',
        'Wiki snapshot과 현재 Knowledge Revision의 정확한 원문 참조를 확인하세요.', 4)


def _uuid(value):
    if not isinstance(value, str) or request_id(value) != value:
        _fail()
    return value


def _text_hash(value):
    return sha256(value.encode('utf-8')).hexdigest()


def _evidence(value):
    if not isinstance(value, dict):
        _fail()
    _uuid(value.get('information_id'))
    data_id(value.get('data_id'))
    start, end, quote = value.get('char_start'), value.get('char_end'), value.get('quote')
    if (type(start) is not int or type(end) is not int or not 0 <= start <= end
            or not isinstance(quote, str) or '\x00' in quote or len(quote) != end - start):
        _fail()
    if value.get('media_sha256') is not None:
        data_id(value['media_sha256'])
    return value


def _source_label(evidence):
    refs = evidence.get('source_refs', [])
    if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
        _fail()
    return (str(evidence.get('source_block_id', '')).startswith('/original_page_facsimile/')
        or any(str(ref.get('block_id', '')).startswith('/original_page_facsimile/')
            or ref.get('source_collection') == 'original_page_facsimile'
            or ref.get('facsimile_provenance') is not None
            or ref.get('derived_primary') is True for ref in refs))


def _match(wiki, grounding, evidence_index):
    start = max(wiki['char_start'], grounding['char_start'])
    end = min(wiki['char_end'], grounding['char_end'])
    quote = ''
    if start < end:
        quote = wiki['quote'][start - wiki['char_start']:end - wiki['char_start']]
        other = grounding['quote'][start - grounding['char_start']:end - grounding['char_start']]
        if quote != other:
            _fail()
    same_image = wiki.get('media_sha256') is not None and wiki.get('media_sha256') == grounding.get('media_sha256')
    if start < end and quote.strip() and not _source_label(wiki) and not _source_label(grounding):
        kind = ('exact_text_range' if (wiki['char_start'], wiki['char_end']) ==
                (grounding['char_start'], grounding['char_end']) else 'overlapping_text_range')
    elif same_image:
        kind, start, end, quote = 'shared_image', None, None, ''
    else:
        return None
    return {'wiki_evidence_index': evidence_index, 'grounding_id': grounding['grounding_id'],
        'information_id': wiki['information_id'], 'data_id': wiki['data_id'],
        'overlap_start': start, 'overlap_end': end, 'quote': quote,
        'quote_sha256': _text_hash(quote),
        'media_sha256': wiki.get('media_sha256') if same_image else None, 'match_kind': kind}


def build_related_links(paper_snapshots: list[dict], graph: dict,
                        review_annotations: list[dict] = None) -> list[dict]:
    """Build reproducible navigation links from a caller-verified source graph.

    The caller owns DB freshness, canonical I/media ownership and persistence.
    Shared quotes and images cannot establish that the Knowledge supports a
    Wiki sentence. Historical groundings are excluded; legacy origins are kept.
    """
    if (not isinstance(paper_snapshots, list) or not isinstance(graph, dict)
            or graph.get('schema_version') != 'knowledge-graph-v1'
            or not isinstance(graph.get('nodes'), list) or not isinstance(graph.get('groundings'), list)
            or type(graph.get('state_version')) is not int or graph['state_version'] < 0):
        _fail()
    annotations = [] if review_annotations is None else review_annotations
    if not isinstance(annotations, list):
        _fail()
    by_revision, node_ids = {}, set()
    for node in graph['nodes']:
        if not isinstance(node, dict):
            _fail()
        revision, node_id = _uuid(node.get('knode_revision_id')), _uuid(node.get('knode_id'))
        if node.get('current_revision_id') != revision or revision in by_revision or node_id in node_ids:
            _fail()
        data_id(node.get('content_fingerprint'))
        by_revision[revision] = node
        node_ids.add(node_id)
    annotation_index = defaultdict(list)
    for annotation in annotations:
        if not isinstance(annotation, dict):
            _fail()
        revision = _uuid(annotation.get('node_revision_id'))
        if revision in by_revision:
            if annotation.get('knode_id', by_revision[revision]['knode_id']) != by_revision[revision]['knode_id']:
                _fail()
            annotation_index[revision].append(deepcopy(annotation))
    for entries in annotation_index.values():
        entries.sort(key=digest)
    grounding_index, grounding_ids = defaultdict(list), set()
    for grounding in graph['groundings']:
        if not isinstance(grounding, dict):
            _fail()
        if grounding.get('node_revision_id') not in by_revision:
            continue
        _evidence(grounding)
        identifier = _uuid(grounding.get('grounding_id'))
        if identifier in grounding_ids:
            _fail()
        grounding_ids.add(identifier)
        grounding_index[(grounding['data_id'], grounding['information_id'])].append(grounding)
    result, snapshot_ids = [], set()
    for paper in paper_snapshots:
        if not isinstance(paper, dict) or paper.get('kind', 'paper') != 'paper':
            _fail()
        snapshot_id, page_id = _uuid(paper.get('snapshot_id')), _uuid(paper.get('page_id'))
        source_id = data_id(paper.get('data_id'))
        if snapshot_id in snapshot_ids or not isinstance(paper.get('items'), list):
            _fail()
        snapshot_ids.add(snapshot_id)
        item_keys = set()
        for item in paper['items']:
            if (not isinstance(item, dict) or not isinstance(item.get('item_key'), str)
                    or not item['item_key'] or item['item_key'] in item_keys
                    or not isinstance(item.get('text'), str) or not item['text'].strip()
                    or '\x00' in item['text'] or not isinstance(item.get('evidence'), list)):
                _fail()
            item_keys.add(item['item_key'])
            matches = defaultdict(list)
            for index, evidence in enumerate(item['evidence']):
                _evidence(evidence)
                if evidence['data_id'] != source_id:
                    _fail()
                _source_label(evidence)
                for grounding in grounding_index[(source_id, evidence['information_id'])]:
                    match = _match(evidence, grounding, index)
                    if match is not None:
                        matches[grounding['node_revision_id']].append(match)
            for revision, entries in matches.items():
                entries.sort(key=lambda match: (match['wiki_evidence_index'], match['grounding_id']))
                node = by_revision[revision]
                review = deepcopy(annotation_index[revision])
                link = {'snapshot_id': snapshot_id, 'page_id': page_id, 'data_id': source_id,
                    'item_key': item['item_key'], 'item_text_sha256': _text_hash(item['text']),
                    'knode_id': node['knode_id'], 'knode_revision_id': revision,
                    'content_fingerprint': node['content_fingerprint'],
                    'knowledge_state_version': graph['state_version'], 'node_snapshot': deepcopy(node),
                    'relation': 'shared_source_evidence', 'semantic_support_validated': False,
                    'match_kind': next(kind for kind in ('exact_text_range', 'overlapping_text_range', 'shared_image')
                                       if any(match['match_kind'] == kind for match in entries)),
                    'matches': entries, 'review_annotations': review, 'review_required': bool(review)}
                link['link_sha256'] = digest(link)
                result.append(link)
    result.sort(key=lambda link: (link['snapshot_id'], link['item_key'], link['knode_revision_id']))
    return result
