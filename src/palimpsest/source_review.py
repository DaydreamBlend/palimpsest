"""Source-addressed review coverage, without choosing importance or rewriting I.

Targets enumerate retained addresses. The model identifies meaningful items
within each target; an independent Validator checks semantic completeness.
Neither address coverage nor candidate counts prove that every fact was found.
Runtime must verify the input against canonical provenance before using this
projection, and freeze this manifest with the execution's input snapshot.
"""

from copy import deepcopy
from hashlib import sha256

from .data import data_id, request_id
from .knowledge import (_array, _digest, _enum, _fail, _key, _keys, _object,
                        _text, source_block_ranges)


PROFILE = 'source-review-v1'
DISPOSITIONS = ('selected', 'context_only', 'not_selected', 'needs_review')
CODE = 'invalid_source_review'


def build_manifest(packet):
    """Project every retained block, including image-only and unmapped blocks."""
    if not isinstance(packet, dict) or not isinstance(packet.get('model_input'), dict):
        _fail(CODE)
    units = packet['model_input'].get('information')
    if not isinstance(units, list) or not units:
        _fail(CODE)
    sources = packet.get('sources', [packet])
    owners = {}
    for source in sources:
        owner, execution = data_id(source['data_id']), request_id(source['source_execution_id'])
        for unit in source['model_input']['information']:
            identifier = request_id(unit['information_id'])
            if identifier in owners:
                _fail(CODE)
            owners[identifier] = (owner, execution)
    targets, seen = [], set()
    for unit in units:
        identifier = request_id(unit['information_id'])
        if identifier in seen or identifier not in owners:
            _fail(CODE)
        seen.add(identifier)
        owner, execution = owners[identifier]
        if (unit.get('data_id', owner) != owner or unit.get('source_execution_id', execution) != execution
                or not isinstance(unit.get('content'), str) or not isinstance(unit.get('source_refs'), list)
                or not isinstance(unit.get('media'), list)):
            _fail(CODE)
        refs = {}
        for ref in unit['source_refs']:
            if not isinstance(ref, dict) or not isinstance(ref.get('block_id'), str) or not ref['block_id']:
                _fail(CODE)
            refs.setdefault(ref['block_id'], []).append(deepcopy(ref))
        media = {}
        for asset in unit['media']:
            if not isinstance(asset, dict) or not isinstance(asset.get('source_block_id'), str):
                _fail(CODE)
            media.setdefault(asset['source_block_id'], set()).add(data_id(asset['sha256']))
        ranges = source_block_ranges(unit)
        # Unlocated media remains addressable through its owning I; no locator is invented.
        blocks = list(refs) or [None]
        orphan_media = set(media) - set(refs)
        if refs and orphan_media:
            blocks.append(None)
        for block in blocks:
            selected_refs = refs.get(block, [])
            span = ranges.get(block)
            char_ranges = [list(span)] if span else ([[0, len(unit['content'])]] if block is None and unit['content'] else [])
            hashes = sorted(media.get(block, set()) if block is not None else
                            {sha for key in orphan_media for sha in media[key]})
            known_empty = (not unit['content'] and not hashes) or bool(selected_refs and all(
                isinstance(ref.get('source_text_range'), dict)
                and ref['source_text_range'].get('char_start') == ref['source_text_range'].get('char_end')
                and type(ref['source_text_range'].get('char_start')) is int for ref in selected_refs) and not hashes)
            mapping = ('information_only' if block is None and (char_ranges or hashes) else
                       'mapped' if char_ranges or hashes else 'empty' if known_empty else 'unmapped')
            target = {'information_id': identifier, 'data_id': owner, 'source_execution_id': execution,
                'source_block_id': block, 'source_refs': selected_refs, 'char_ranges': char_ranges,
                'media_sha256s': hashes, 'mapping_status': mapping,
                'content_sha256': sha256(unit['content'].encode('utf-8')).hexdigest()}
            targets.append({'target_id': _digest({'schema_version': PROFILE, **target}), **target})
    if seen != set(owners):
        _fail(CODE)
    result = {'schema_version': PROFILE, 'targets': targets}
    return {**result, 'manifest_sha256': _digest(result)}


def _targets(manifest):
    _keys(manifest, ('schema_version', 'targets', 'manifest_sha256'), CODE)
    if (manifest['schema_version'] != PROFILE or not isinstance(manifest['targets'], list)
            or not manifest['targets'] or manifest['manifest_sha256'] != _digest({
                'schema_version': PROFILE, 'targets': manifest['targets']})):
        _fail('source_review_manifest_changed')
    result = {}
    for target in manifest['targets']:
        _keys(target, ('target_id', 'information_id', 'data_id', 'source_execution_id', 'source_block_id',
                      'source_refs', 'char_ranges', 'media_sha256s', 'mapping_status', 'content_sha256'), CODE)
        identifier = target['target_id']
        if (identifier in result or identifier != _digest({'schema_version': PROFILE,
                **{key: value for key, value in target.items() if key != 'target_id'}})):
            _fail('source_review_manifest_changed')
        result[identifier] = target
    return result


def extend_generation(schema, manifest):
    targets = _targets(manifest)
    anchor = _object({'char_start': {'type': ['integer', 'null'], 'minimum': 0},
        'char_end': {'type': ['integer', 'null'], 'minimum': 0},
        'media_sha256': {'type': ['string', 'null']}})
    item = _object({'item_key': {'type': 'string'}, 'label': {'type': 'string', 'minLength': 1},
        'disposition': _enum(DISPOSITIONS), 'candidate_keys': _array({'type': 'string'}),
        'anchors': _array(anchor), 'reason': {'type': 'string', 'minLength': 1}})
    result = deepcopy(schema)
    result['properties']['source_reviews'] = _array(_object({
        'target_id': _enum(targets), 'items': _array(item, nonempty=True)}), nonempty=True)
    result['required'] = list(dict.fromkeys([*result['required'], 'source_reviews']))
    return result


def _anchor(anchor, target):
    _keys(anchor, ('char_start', 'char_end', 'media_sha256'), CODE)
    start, end, media = anchor['char_start'], anchor['char_end'], anchor['media_sha256']
    if media is not None:
        if start is not None or end is not None or media not in target['media_sha256s']:
            _fail('source_review_anchor_mismatch')
    elif (type(start) is not int or type(end) is not int or not start < end
          or not any(lo <= start < end <= hi for lo, hi in target['char_ranges'])):
        _fail('source_review_anchor_mismatch')
    return deepcopy(anchor)


def _covers(citation, anchor, target):
    if (citation.get('information_id') != target['information_id']
            or citation.get('data_id', target['data_id']) != target['data_id']
            or citation.get('source_execution_id', target['source_execution_id']) != target['source_execution_id']):
        return False
    if anchor['media_sha256'] is not None:
        return citation.get('media_sha256') == anchor['media_sha256']
    start, end = citation.get('char_start'), citation.get('char_end')
    return (type(start) is int and type(end) is int
            and start <= anchor['char_start'] < anchor['char_end'] <= end)


def normalize_generation(response, manifest, normalized_candidates):
    targets = _targets(manifest)
    rows = response.get('source_reviews')
    if not isinstance(rows, list) or type(response.get('complete')) is not bool:
        _fail(CODE)
    candidates = {node['candidate_key']: node for node in normalized_candidates}
    if len(candidates) != len(normalized_candidates):
        _fail(CODE)
    seen, items_seen, result = set(), set(), []
    for row in rows:
        _keys(row, ('target_id', 'items'), CODE)
        identifier = row['target_id']
        if not isinstance(identifier, str) or identifier not in targets or identifier in seen:
            _fail('source_review_target_coverage_mismatch')
        seen.add(identifier)
        if not isinstance(row['items'], list) or not row['items']:
            _fail(CODE)
        target, items = targets[identifier], []
        for item in row['items']:
            _keys(item, ('item_key', 'label', 'disposition', 'candidate_keys', 'anchors', 'reason'), CODE)
            key = _key(item['item_key'], CODE)
            if key in items_seen:
                _fail('source_review_duplicate_item')
            items_seen.add(key)
            disposition, keys = item['disposition'], item['candidate_keys']
            if (disposition not in DISPOSITIONS or not isinstance(keys, list)
                    or any(not isinstance(k, str) or k not in candidates for k in keys)
                    or len(keys) != len(set(keys)) or (disposition == 'selected' and not keys)
                    or (disposition in ('context_only', 'not_selected') and keys)
                    or (response['complete'] and disposition == 'needs_review')):
                _fail('source_review_disposition_mismatch')
            if not isinstance(item['anchors'], list):
                _fail(CODE)
            anchors = [_anchor(anchor, target) for anchor in item['anchors']]
            if len({_digest(anchor) for anchor in anchors}) != len(anchors):
                _fail('source_review_anchor_mismatch')
            if not anchors and (keys or not (target['mapping_status'] == 'empty'
                    or (target['mapping_status'] == 'unmapped' and disposition == 'needs_review'))):
                _fail('source_review_anchor_required')
            if keys:
                # Each linked candidate must cover an item anchor, and their evidence
                # together must cover every anchor. This is address binding, not truth.
                coverage = [[any(_covers(citation, anchor, target) for citation in candidates[k]['evidence'])
                             for anchor in anchors] for k in keys]
                if not all(any(row) for row in coverage) or not all(any(row[i] for row in coverage) for i in range(len(anchors))):
                    _fail('source_review_candidate_evidence_mismatch')
            items.append({**deepcopy(item), 'label': _text(item['label'], code=CODE),
                          'reason': _text(item['reason'], code=CODE), 'anchors': anchors})
        result.append({'target_id': identifier, 'items': items})
    if seen != set(targets):
        _fail('source_review_target_coverage_mismatch')
    for candidate in normalized_candidates:
        linked = [(targets[row['target_id']], anchor) for row in result for item in row['items']
                  if candidate['candidate_key'] in item['candidate_keys'] for anchor in item['anchors']]
        if not linked or not candidate['evidence']:
            _fail('source_review_candidate_unrepresented')
        for citation in candidate['evidence']:
            modalities = ([False] if type(citation.get('char_start')) is int
                and type(citation.get('char_end')) is int and citation['char_start'] < citation['char_end'] else [])
            if citation.get('media_sha256') is not None:
                modalities.append(True)
            if not modalities or any(not any((anchor['media_sha256'] is not None) == image
                    and _covers(citation, anchor, target) for target, anchor in linked) for image in modalities):
                _fail('source_review_candidate_unrepresented')
    ordered = {row['target_id']: row for row in result}
    return [ordered[key] for key in targets]


def _items(reviews, targets):
    if not isinstance(reviews, list) or len(reviews) != len(targets):
        _fail('source_review_target_coverage_mismatch')
    result, seen = {}, set()
    for row in reviews:
        if row['target_id'] not in targets or row['target_id'] in seen or not row['items']:
            _fail('source_review_target_coverage_mismatch')
        seen.add(row['target_id'])
        for item in row['items']:
            if item['item_key'] in result:
                _fail('source_review_duplicate_item')
            result[item['item_key']] = (row['target_id'], item)
    return result


def extend_validation(schema, manifest, reviews):
    targets = _targets(manifest)
    items = _items(reviews, targets)
    def decision(key, ids):
        return _array(_object({key: _enum(ids), 'verdict': _enum(('confirmed', 'needs_review')),
                              'reason': {'type': 'string', 'minLength': 1}}), nonempty=True)
    result = deepcopy(schema)
    result['properties']['source_review_decisions'] = _object({
        'targets': decision('target_id', targets), 'items': decision('item_key', items)})
    result['required'] = list(dict.fromkeys([*result['required'], 'source_review_decisions']))
    return result


def validate_decisions(response, manifest, reviews, validated_candidates):
    targets = _targets(manifest)
    items = _items(reviews, targets)
    value = response.get('source_review_decisions')
    _keys(value, ('targets', 'items'), CODE)
    decisions = {}
    for collection, key, expected in (('targets', 'target_id', targets), ('items', 'item_key', items)):
        if not isinstance(value[collection], list):
            _fail(CODE)
        mapped = {}
        for row in value[collection]:
            _keys(row, (key, 'verdict', 'reason'), CODE)
            identifier = row[key]
            if (not isinstance(identifier, str) or identifier not in expected or identifier in mapped
                    or row['verdict'] not in ('confirmed', 'needs_review')):
                _fail('source_review_decision_coverage_mismatch')
            mapped[identifier] = {**deepcopy(row), 'reason': _text(row['reason'], code=CODE)}
        if set(mapped) != set(expected):
            _fail('source_review_decision_coverage_mismatch')
        decisions[collection] = mapped
    pending_targets = {key for key, row in decisions['targets'].items() if row['verdict'] == 'needs_review'}
    pending_items = set()
    for key, (target_id, item) in items.items():
        if (decisions['items'][key]['verdict'] == 'needs_review' or item['disposition'] == 'needs_review'
                or any(validated_candidates.get(candidate, {}).get('verdict') not in ('accepted', 'reused')
                       for candidate in item['candidate_keys'])):
            pending_items.add(key)
            pending_targets.add(target_id)
    return {'targets': [decisions['targets'][key] for key in targets],
        'items': [decisions['items'][key] for key in items],
        'pending_target_ids': [key for key in targets if key in pending_targets],
        'pending_item_keys': [key for key in items if key in pending_items]}
