"""Source-grounded paper/topic read projections, without K or publication writes.

The caller verifies canonical source membership and actual model delivery, then
selects accepted items for rendering. Rendering does not approve their meaning.
"""

from copy import deepcopy
import html
import json
import re
import unicodedata

from .data import data_id
from .errors import PalimpsestError
from .knowledge import (KEY_PATTERN, SOURCE_ROLES, _array, _digest, _enum, _key, _keys,
                        _object, _strings, _text, _uuid, normalize_evidence, source_block_ranges)
from .multi_source_i2k import combine_packets


PROFILE = 'source-grounded-paper-wiki-v1'
SECTIONS = ('overview', 'methods', 'findings', 'limitations')
SECTION_TITLES = {'overview': '개요', 'methods': '방법', 'findings': '주요 결과', 'limitations': '한계'}
TOPIC_KEY_PATTERN = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
REVIEW_DISPOSITIONS = ('used', 'context_only', 'not_selected', 'needs_review')
VERDICTS = ('accepted', 'rejected', 'needs_review')
ITEM_CHECKS = ('source_supported', 'citations_sufficient', 'scope_preserved', 'no_new_inference')


def _error(code='invalid_paper_wiki_proposal'):
    raise PalimpsestError(code, '논문 위키의 구조·원문 근거·주제·전체 검토 범위를 확인하세요.', 4)


def _topic_key(value):
    if not isinstance(value, str) or len(value) > 80 or re.fullmatch(TOPIC_KEY_PATTERN, value) is None:
        _error('invalid_paper_wiki_topic')
    return value


def _topics(values):
    if not isinstance(values, list):
        _error('invalid_paper_wiki_topic')
    result = {}
    for value in values:
        _keys(value, ('topic_key', 'title', 'scope'), 'invalid_paper_wiki_topic')
        key = _topic_key(value['topic_key'])
        if key in result:
            _error('duplicate_paper_wiki_topic')
        _text(value['title'])
        _text(value['scope'])
        # Existing topic definitions are frozen catalog values, not names the
        # model may normalize, trim, rename or reinterpret while reusing a key.
        result[key] = deepcopy(value)
    return result


def _input(packet):
    # Reuse the full-source packet/hash/media checks. DB verification remains
    # the caller's responsibility; a supplied hash is not source authority.
    bundle = combine_packets([packet])
    return {unit['information_id']: unit for unit in bundle['model_input']['information']}


def _evidence_schema(packet, units):
    evidence = _object({'information_id': _enum(units), 'quote': {'type': 'string'},
        'media_sha256': _enum([asset['sha256'] for asset in packet['media_assets']], nullable=True),
        'source_role': _enum(SOURCE_ROLES)})
    blocks = list(dict.fromkeys(block for unit in units.values() for block in source_block_ranges(unit)))
    if blocks:
        evidence = {'anyOf': [evidence, _object({'information_id': _enum(units),
            'source_block_id': _enum(blocks), 'source_role': _enum(SOURCE_ROLES)})]}
    return evidence


def _review_schema(units):
    return _array(_object({'information_id': _enum(units), 'disposition': _enum(REVIEW_DISPOSITIONS),
                           'reason': {'type': 'string', 'minLength': 1}}))


def generation_schema(packet, existing_topics):
    units = _input(packet)
    _topics(existing_topics)
    text = {'type': 'string', 'minLength': 1}
    topic_key = {'type': 'string', 'pattern': TOPIC_KEY_PATTERN, 'maxLength': 80}
    evidence = _evidence_schema(packet, units)
    return _object({
        'items': _array(_object({'item_key': {'type': 'string', 'pattern': KEY_PATTERN},
            'section': _enum(SECTIONS), 'text': text, 'evidence': _array(evidence, nonempty=True),
            'topic_keys': _array(topic_key)}), nonempty=True),
        'topics': _array(_object({'topic_key': topic_key, 'title': text, 'scope': text})),
        'reviews': _review_schema(units),
        'complete': {'type': 'boolean'}, 'issues': _array(text),
    })


def _citation(value, units):
    citation = normalize_evidence(value, units, allow_media_only=True, allow_block_refs=True)
    unit = units[citation['information_id']]
    ranges = source_block_ranges(unit)
    selected = set()
    if citation['quote']:
        start, end = citation['char_start'], citation['char_end']
        spans = sorted((max(start, a), min(end, b), block) for block, (a, b) in ranges.items()
                       if a < end and b > start)
        position = start
        for a, b, block in spans:
            if unit['content'][position:a].strip():
                _error('paper_wiki_citation_locus_missing')
            selected.add(block)
            position = max(position, b)
        if not spans or unit['content'][position:end].strip():
            _error('paper_wiki_citation_locus_missing')
    if citation['media_sha256'] is not None:
        media = [asset for asset in unit['media'] if asset['sha256'] == citation['media_sha256']]
        if any(not isinstance(asset.get('source_block_id'), str) for asset in media):
            _error('paper_wiki_citation_locus_missing')
        selected.update(asset['source_block_id'] for asset in media)
    refs = [ref for ref in unit['source_refs'] if ref.get('block_id') in selected]
    if not selected or len(refs) != len(selected) or {ref['block_id'] for ref in refs} != selected:
        _error('paper_wiki_citation_locus_missing')
    pages = []
    for ref in refs:
        page = ref.get('page_index')
        if page is not None:
            if type(page) is not int or page < 0:
                _error('paper_wiki_citation_locus_missing')
            pages.append(page + 1)
    return {**citation, 'data_id': unit['data_id'], 'source_execution_id': unit['source_execution_id'],
            'page_numbers': sorted(set(pages)), 'source_refs': deepcopy(refs)}


def normalize_proposal(response, packet, existing_topics):
    units = _input(packet)
    existing = _topics(existing_topics)
    _keys(response, ('items', 'topics', 'reviews', 'complete', 'issues'), 'invalid_paper_wiki_proposal')
    if type(response['complete']) is not bool or not isinstance(response['items'], list) or not response['items']:
        _error()
    topics = _topics(response['topics'])
    for key, topic in topics.items():
        if key in existing and topic != existing[key]:
            _error('paper_wiki_topic_catalog_mismatch')
    items, keys, used, referenced_topics = [], set(), set(), set()
    for value in response['items']:
        _keys(value, ('item_key', 'section', 'text', 'evidence', 'topic_keys'), 'invalid_paper_wiki_item')
        key = _key(value['item_key'], 'invalid_paper_wiki_item')
        if key in keys or value['section'] not in SECTIONS:
            _error('invalid_paper_wiki_item')
        keys.add(key)
        topic_keys = value['topic_keys']
        if not isinstance(topic_keys, list):
            _error('invalid_paper_wiki_topic')
        topic_keys = [_topic_key(key) for key in topic_keys]
        if len(topic_keys) != len(set(topic_keys)) or not set(topic_keys) <= topics.keys():
            _error('paper_wiki_topic_reference_mismatch')
        if not isinstance(value['evidence'], list) or not value['evidence']:
            _error('invalid_paper_wiki_evidence')
        citations, seen = [], set()
        for evidence in value['evidence']:
            citation = _citation(evidence, units)
            marker = tuple(citation[name] for name in
                           ('information_id', 'char_start', 'char_end', 'media_sha256', 'source_role'))
            if marker in seen:
                _error('duplicate_paper_wiki_evidence')
            seen.add(marker)
            used.add(citation['information_id'])
            citations.append(citation)
        referenced_topics.update(topic_keys)
        items.append({**deepcopy(value), 'text': _text(value['text']), 'evidence': citations,
                      'topic_keys': topic_keys})
    if not any(item['section'] in ('overview', 'findings') for item in items):
        _error('paper_wiki_summary_required')
    if referenced_topics != topics.keys():
        _error('paper_wiki_unused_topic')
    reviews = _normalize_reviews(response['reviews'], units, used, response['complete'])
    return {'items': items, 'topics': list(topics.values()), 'reviews': reviews,
            'complete': response['complete'], 'issues': _strings(response['issues'])}


def _normalize_reviews(values, units, used, complete):
    if not isinstance(values, list):
        _error('invalid_paper_wiki_review')
    if not used <= units.keys():
        _error('paper_wiki_review_evidence_mismatch')
    reviews = {}
    for value in values:
        _keys(value, ('information_id', 'disposition', 'reason'), 'invalid_paper_wiki_review')
        identifier = value['information_id']
        if not isinstance(identifier, str) or identifier not in units or identifier in reviews:
            _error('paper_wiki_review_coverage_mismatch')
        disposition = value['disposition']
        if disposition not in REVIEW_DISPOSITIONS or ((identifier in used) != (disposition == 'used')):
            _error('paper_wiki_review_evidence_mismatch')
        reviews[identifier] = {**deepcopy(value), 'reason': _text(value['reason'])}
    if reviews.keys() != units.keys():
        _error('paper_wiki_review_coverage_mismatch')
    if complete and any(value['disposition'] == 'needs_review' for value in reviews.values()):
        _error('paper_wiki_unresolved_review')
    return [reviews[key] for key in units]


def _base_items(base_proposal):
    _keys(base_proposal, ('items', 'topics', 'reviews', 'complete', 'issues'), 'invalid_paper_wiki_repair_base')
    values = base_proposal['items']
    if not isinstance(values, list) or not values:
        _error('invalid_paper_wiki_repair_base')
    items = {}
    for item in values:
        _keys(item, ('item_key', 'section', 'text', 'evidence', 'topic_keys'), 'invalid_paper_wiki_repair_base')
        key = _key(item['item_key'], 'invalid_paper_wiki_repair_base')
        if key in items:
            _error('invalid_paper_wiki_repair_base')
        items[key] = item
    return items


def _editable_keys(values, items):
    if values is None:
        return []
    if (not isinstance(values, list) or any(not isinstance(key, str) or key not in items for key in values)
            or len(values) != len(set(values))):
        _error('invalid_paper_wiki_editable_items')
    return list(values)


def citation_repair_schema(packet, base_proposal, *, editable_item_keys=None):
    """Allow extra citations and only explicitly authorized item text changes."""
    units = _input(packet)
    items = _base_items(base_proposal)
    editable = _editable_keys(editable_item_keys, items)
    properties = {'additions': _array(_object({
        'item_key': _enum(items),
        'evidence': _array(_evidence_schema(packet, units), nonempty=True),
    })), 'reviews': _review_schema(units), 'complete': {'type': 'boolean'},
        'issues': _array({'type': 'string', 'minLength': 1})}
    if editable:
        properties['text_changes'] = _array(_object({'item_key': _enum(editable),
                                                    'text': {'type': 'string', 'minLength': 1}}))
    return _object(properties)


def normalize_citation_repair(response, packet, base_proposal, *, editable_item_keys=None):
    """Append evidence and apply scoped text edits, retaining every old citation.

    Runtime must bind the normalized base to its stored hash and the same source
    snapshot and authorize editable keys before calling. With no editable keys,
    every item text is fixed. Existing evidence and topics are never normalized
    again or replaced; the complete result still needs fresh semantic validation.
    """
    units = _input(packet)
    items = deepcopy(_base_items(base_proposal))
    editable = _editable_keys(editable_item_keys, items)
    fields = ('additions', 'reviews', 'complete', 'issues') + (('text_changes',) if editable else ())
    _keys(response, fields, 'invalid_paper_wiki_citation_repair')
    if type(response['complete']) is not bool or not isinstance(response['additions'], list):
        _error('invalid_paper_wiki_citation_repair')
    text_changed = False
    if editable:
        if not isinstance(response['text_changes'], list):
            _error('invalid_paper_wiki_citation_repair')
        changed_keys = set()
        for change in response['text_changes']:
            _keys(change, ('item_key', 'text'), 'invalid_paper_wiki_citation_repair')
            key = change['item_key']
            if not isinstance(key, str) or key not in editable or key in changed_keys:
                _error('paper_wiki_repair_item_mismatch')
            changed_keys.add(key)
            text = _text(change['text'], code='invalid_paper_wiki_citation_repair')
            text_changed = text_changed or text != items[key]['text']
            items[key]['text'] = text
    seen_items = set()
    # A role relabel alone is not new evidence. Distinct repeated-text ranges
    # remain distinct, as do text evidence and owned image evidence.
    def locus(citation):
        return tuple(citation[key] for key in ('information_id', 'char_start', 'char_end', 'media_sha256'))

    for addition in response['additions']:
        _keys(addition, ('item_key', 'evidence'), 'invalid_paper_wiki_citation_repair')
        key = addition['item_key']
        if not isinstance(key, str) or key not in items or key in seen_items:
            _error('paper_wiki_repair_item_mismatch')
        if not isinstance(addition['evidence'], list) or not addition['evidence']:
            _error('invalid_paper_wiki_citation_repair')
        seen_items.add(key)
        item = items[key]
        existing = {locus(citation) for citation in item['evidence']}
        for value in addition['evidence']:
            citation = _citation(value, units)
            marker = locus(citation)
            if marker in existing:
                _error('duplicate_paper_wiki_evidence')
            existing.add(marker)
            item['evidence'].append(citation)
    if response['complete'] and not response['additions'] and not text_changed:
        _error('invalid_paper_wiki_citation_repair')
    used = {citation['information_id'] for item in items.values() for citation in item['evidence']}
    reviews = _normalize_reviews(response['reviews'], units, used, response['complete'])
    return {'items': list(items.values()), 'topics': deepcopy(base_proposal['topics']), 'reviews': reviews,
            'complete': response['complete'], 'issues': _strings(response['issues'])}


def validation_schema(normalized):
    text = {'type': 'string', 'minLength': 1}
    item = _object({'item_key': _enum([value['item_key'] for value in normalized['items']]),
        'verdict': _enum(VERDICTS), **{name: {'type': 'boolean'} for name in ITEM_CHECKS}, 'reason': text})
    keys = [value['topic_key'] for value in normalized['topics']]
    topic = _object({'topic_key': _enum(keys) if keys else {'type': 'string'},
                    'verdict': _enum(VERDICTS), 'meaning_correct': {'type': 'boolean'}, 'reason': text})
    topics = _array(topic)
    if not keys:
        topics['maxItems'] = 0
    return _object({'items': _array(item), 'topics': topics, 'complete': {'type': 'boolean'}, 'issues': _array(text)})


def validate_decisions(response, normalized):
    _keys(response, ('items', 'topics', 'complete', 'issues'), 'invalid_paper_wiki_decision')
    if type(response['complete']) is not bool:
        _error('invalid_paper_wiki_decision')
    result = {'complete': response['complete'], 'issues': _strings(response['issues'])}
    for collection, key_name, checks in (('items', 'item_key', ITEM_CHECKS),
                                         ('topics', 'topic_key', ('meaning_correct',))):
        expected = [value[key_name] for value in normalized[collection]]
        values = response[collection]
        if not isinstance(values, list):
            _error('invalid_paper_wiki_decision')
        decisions = {}
        for value in values:
            _keys(value, (key_name, 'verdict', *checks, 'reason'), 'invalid_paper_wiki_decision')
            key = value[key_name]
            if not isinstance(key, str) or key not in expected or key in decisions:
                _error('paper_wiki_decision_coverage_mismatch')
            if value['verdict'] not in VERDICTS or any(type(value[name]) is not bool for name in checks):
                _error('invalid_paper_wiki_decision')
            if value['verdict'] == 'accepted' and not all(value[name] for name in checks):
                _error('paper_wiki_acceptance_not_supported')
            if response['complete'] and value['verdict'] == 'needs_review':
                _error('paper_wiki_unresolved_review')
            decisions[key] = {**deepcopy(value), 'reason': _text(value['reason'])}
        if decisions.keys() != set(expected):
            _error('paper_wiki_decision_coverage_mismatch')
        result[collection] = [decisions[key] for key in expected]
    return result


def _inline(value):
    """Treat model/source prose as text, never Markdown structure or HTML."""
    value = ' '.join(_text(value, empty=True).split())
    value = ''.join(f'\\u{ord(char):04x}' if unicodedata.category(char) in ('Cc', 'Cf') else char for char in value)
    value = html.escape(value, quote=False)
    return re.sub(r'([\\`*_\[\]{}#!|+\-.])', r'\\\1', value)


escape_text = _inline


def _frontmatter(page, kind):
    snapshot = page.get('snapshot_id')
    fields = {'page_id': _uuid(page['page_id'], 'invalid_paper_wiki_page'),
              'snapshot_id': _uuid(snapshot, 'invalid_paper_wiki_page') if snapshot is not None else None,
              'kind': kind, 'title': _text(page['title']), 'canonical': False}
    return ['---', *(f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in fields.items()), '---', '']


def _link(catalog, collection, key):
    try:
        entry = catalog[collection][key]
        identifier = _uuid(entry['page_id'], 'invalid_paper_wiki_catalog')
        title = _text(entry['title'])
    except (KeyError, TypeError):
        _error('invalid_paper_wiki_catalog')
    label = _inline(title).replace(r'\[', '&#91;').replace(r'\]', '&#93;').replace(r'\|', '&#124;')
    return f'[[{collection}/{identifier}|{label}]]'


def _metadata(page):
    identifier = _uuid(page['page_id'], 'invalid_paper_wiki_page')
    lines = [f'- Page: `{identifier}`']
    if page.get('snapshot_id') is not None:
        lines.append(f"- Snapshot: `{_uuid(page['snapshot_id'], 'invalid_paper_wiki_page')}`")
    metadata = page.get('metadata', {})
    if not isinstance(metadata, dict) or any(not isinstance(key, str) for key in metadata):
        _error('invalid_paper_wiki_page')
    for key in sorted(metadata):
        value = metadata[key] if isinstance(metadata[key], str) else json.dumps(metadata[key], ensure_ascii=False, sort_keys=True, allow_nan=False)
        lines.append(f'- {_inline(key)}: {_inline(value)}')
    return lines


def _items_markdown(items, owner, citations):
    keys = set()
    lines = []
    for item in items:
        key = _key(item['item_key'], 'invalid_paper_wiki_item')
        if key in keys or item['section'] not in SECTIONS or not item['evidence']:
            _error('invalid_paper_wiki_item')
        keys.add(key)
        if any(citation['data_id'] != owner for citation in item['evidence']):
            _error('paper_wiki_citation_owner_mismatch')
    for section in SECTIONS:
        selected = [item for item in items if item['section'] == section]
        if not selected:
            continue
        lines.extend([f'## {SECTION_TITLES[section]}', ''])
        for item in selected:
            markers = []
            for citation in item['evidence']:
                key = _digest(citation)
                if key not in citations:
                    citations[key] = (len(citations) + 1, citation)
                markers.append(f"[^s{citations[key][0]}]")
            lines.extend([_inline(item['text']) + ' ' + ''.join(markers), ''])
    return lines


def _citations_markdown(citations):
    lines = ['## 출처', '']
    for number, citation in citations.values():
        owner = data_id(citation['data_id'])
        identifier = _uuid(citation['information_id'], 'invalid_paper_wiki_evidence')
        execution = _uuid(citation['source_execution_id'], 'invalid_paper_wiki_evidence')
        start, end, quote = citation['char_start'], citation['char_end'], citation['quote']
        if type(start) is not int or type(end) is not int or start < 0 or end < start or len(quote) != end - start:
            _error('invalid_paper_wiki_evidence')
        lines.extend([f'[^s{number}]: Data `{owner}`; I `{identifier}`; source execution `{execution}`; chars `[{start}, {end})`.', ''])
        for ref in citation['source_refs']:
            page = ref.get('page_index')
            if page is not None and (type(page) is not int or page < 0):
                _error('invalid_paper_wiki_evidence')
            location = f'page {page + 1}' if page is not None else 'text source'
            lines.append(f"    - {_inline(location)}; block {_inline(ref['block_id'])}; locator {_inline(ref['raw_locator'])}; anchor {_inline(ref['anchor_sha256'])}.")
            if page is not None:
                lines.append(f'    - [원본 PDF p.{page + 1}](../originals/{owner}.pdf#page={page + 1})')
            for field in ('bbox', 'text_range', 'source_text_range'):
                if ref.get(field) is not None:
                    lines.append(f'    - {field}: {_inline(json.dumps(ref[field], ensure_ascii=False, sort_keys=True))}')
        if citation.get('media_sha256') is not None:
            lines.append(f"    - Image SHA-256: `{data_id(citation['media_sha256'])}`")
        if quote:
            fence = '`' * max(3, max((len(run) for run in re.findall(r'`+', quote)), default=0) + 1)
            lines.extend(['', f'    {fence}text'])
            lines.extend('    ' + line for line in quote.split('\n'))
            lines.append('    ' + fence)
        lines.append('')
    return lines


def render_paper(page, catalog):
    """Render caller-selected normalized items; no semantic acceptance or I/O."""
    owner = data_id(page['data_id'])
    topics = _topics(page['topics'])
    if any(not set(item['topic_keys']) <= topics.keys() for item in page['items']):
        _error('paper_wiki_topic_reference_mismatch')
    lines = [*_frontmatter(page, page.get('source_format', 'paper')), f"# {_inline(page['title'])}", '', *_metadata(page), f'- Data: `{owner}`', '']
    citations = {}
    lines.extend(_items_markdown(page['items'], owner, citations))
    if topics:
        lines.extend(['## 주제', ''])
        lines.extend('- ' + _link(catalog, 'topics', key) for key in sorted(topics))
        lines.append('')
    lines.extend(_citations_markdown(citations))
    return '\n'.join(lines).rstrip() + '\n'


def render_topic(page, catalog):
    """Aggregate each paper's already selected items without cross-paper synthesis."""
    topic_key = _topic_key(page['topic_key'])
    lines = [*_frontmatter(page, 'topic'), f"# {_inline(page['title'])}", '', _inline(page['scope']), '', *_metadata(page), '']
    citations, seen = {}, set()
    for contribution in sorted(page['contributions'], key=lambda value: value['paper_data_id']):
        owner = data_id(contribution['paper_data_id'])
        paper_id = _uuid(contribution['paper_page_id'], 'invalid_paper_wiki_page')
        if owner in seen or any(topic_key not in item['topic_keys'] for item in contribution['items']):
            _error('paper_wiki_topic_reference_mismatch')
        seen.add(owner)
        if catalog.get('papers', {}).get(owner, {}).get('page_id') != paper_id:
            _error('invalid_paper_wiki_catalog')
        lines.extend([f"## {_inline(contribution['paper_title'])}", '', _link(catalog, 'papers', owner), ''])
        item_lines = _items_markdown(contribution['items'], owner, citations)
        lines.extend('#' + line if line.startswith('## ') else line for line in item_lines)
    lines.extend(_citations_markdown(citations))
    return '\n'.join(lines).rstrip() + '\n'
