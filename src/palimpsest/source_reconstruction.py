"""Reconstruct retained source blocks and locate I in D; no file or model I/O."""

from copy import deepcopy
from hashlib import sha256
import math
import re

from .errors import PalimpsestError
from .i2k import digest
from .source_pages import PAGE_COLLECTION, parent_bundle


def _fail(code='source_reconstruction_mismatch'):
    raise PalimpsestError(code, '선택한 원문 실행과 위치·복원 범위를 확인하세요.', 4)


def _full_packet(packet):
    if (packet.get('schema_version') != 'i2k-input-v1'
            or packet.get('input_sha256') != digest({k:v for k,v in packet.items() if k != 'input_sha256'})
            or packet.get('context_information_ids') or packet.get('excluded_information_ids')
            or packet['target_information_ids'] != [u['information_id'] for u in packet['model_input']['information']]
            or any(u['role'] != 'target' for u in packet['model_input']['information'])):
        _fail('full_source_input_required')


def build_reconstruction(bundle, rows, packet, original):
    """Independently recover the exact retained blocks from canonical I payloads."""
    _full_packet(packet)
    if (packet['source_bundle_sha256'] != digest(bundle) or original['data_id'] != packet['data_id']
            or original['artifact_path'] != f"objects/sha256/{packet['data_id'][:2]}/{packet['data_id']}"
            or {str(r['information_id']) for r in rows} != set(packet['target_information_ids'])):
        _fail()
    recovered = {}
    units = {u['information_id']:u for u in packet['model_input']['information']}
    for row in rows:
        unit = units[str(row['information_id'])]
        if any(row[k] != unit[k] for k in ('title','content','kind','unit_type','identity_fingerprint','content_fingerprint')):
            _fail()
        for block in row['payload']['source_blocks']:
            if block['block_id'] in recovered:
                _fail()
            recovered[block['block_id']] = deepcopy(block)
    blocks = [recovered.pop(b['block_id'], None) for b in bundle['blocks']]
    if recovered or blocks != bundle['blocks']:
        _fail()
    facsimiles = [b for b in blocks if b.get('source_collection') == PAGE_COLLECTION]
    if facsimiles:
        parent_bundle(bundle)
    markdown = bundle.get('coordinate_system') == 'text_ranges'
    text_exact = markdown and sha256(''.join(b['text'] for b in blocks).encode('utf-8')).hexdigest() == original['data_id']
    if markdown and not text_exact:
        _fail()
    result = {'schema_version':'source-reconstruction-v1', 'source_execution_id':packet['source_execution_id'],
        'data_id':packet['data_id'], 'input_sha256':packet['input_sha256'],
        'source_bundle_sha256':packet['source_bundle_sha256'], 'parse_manifest_sha256':packet['parse_manifest_sha256'],
        'original':{k:original[k] for k in ('data_id','byte_size','artifact_path','media_type')},
        'information_ids':packet['target_information_ids'], 'information_count':len(rows),
        'retained_blocks':blocks, 'retained_block_count':len(blocks),
        'exact_retained_block_coverage':True, 'media_assets':deepcopy(packet['media_assets']),
        'original_page_image_information_count':len(facsimiles),
        'source_coverage':('exact_utf8_source_bytes' if text_exact else
                           'all_rendered_visible_pages_in_information' if facsimiles else 'not_proven'),
        'ocr_text_complete':False if not markdown else None,
        'pdf_byte_reconstruction':'registered_original_artifact' if not markdown else None,
        'limitations':([] if markdown else ['Page images preserve rendered visible content at the recorded resolution; '
            'this is not proof of complete OCR or preservation of hidden PDF objects in I text.']),
        'llm_calls':0,'canonical_writes':0}
    result['reconstruction_sha256'] = digest(result)
    return result


def locate_information(packet, information_id, *, char_range=None):
    """Map an I substring to D refs; assembly-only separators have no source span."""
    _full_packet(packet)
    unit = next((u for u in packet['model_input']['information'] if u['information_id'] == information_id), None)
    if unit is None:
        _fail('i2k_information_scope_mismatch')
    if char_range is not None and (not isinstance(char_range, (list,tuple)) or len(char_range) != 2
            or any(type(n) is not int for n in char_range) or not 0 <= char_range[0] < char_range[1] <= len(unit['content'])):
        _fail('invalid_information_location')
    segments = unit.get('source_assembly', {}).get('content_segments', [])
    selected = []
    for segment in segments:
        start,end = segment['char_start'],segment['char_end']
        if char_range is not None and (start is None or end is None or
                max(start,char_range[0]) >= min(end,char_range[1])):
            continue
        item = deepcopy(segment)
        if char_range is not None:
            lo,hi = max(start,char_range[0]),min(end,char_range[1])
            item['matched_information_char_range'] = [lo,hi]
            if item.get('source_char_range') is not None:
                origin = item['source_char_range'][0]
                item['matched_source_char_range'] = [origin+lo-start,origin+hi-start]
            if item.get('source_text_range') is not None:
                source = item['source_text_range']
                item['matched_source_char_range'] = [source['char_start']+lo-start,source['char_start']+hi-start]
                item['matched_source_byte_range'] = [source['byte_start']+len(unit['content'][start:lo].encode('utf-8')),
                                                      source['byte_start']+len(unit['content'][start:hi].encode('utf-8'))]
            member = item.get('code_context', {}).get('member_text_range')
            if member is not None:
                local_start, local_end = lo-start, hi-start
                text = unit['content'][start:end]
                item['matched_member_char_range'] = [member['char_start']+local_start, member['char_start']+local_end]
                item['matched_member_byte_range'] = [member['byte_start']+len(text[:local_start].encode('utf-8')),
                    member['byte_start']+len(text[:local_end].encode('utf-8'))]
                line_ends = [match.end() for match in re.finditer(r'\r\n|\r|\n', text)]
                item['matched_member_line_range'] = [member['line_start']+sum(stop <= local_start for stop in line_ends),
                    member['line_start']+sum(stop <= max(local_start, local_end-1) for stop in line_ends)]
        selected.append(item)
    if char_range is not None and not segments:
        _fail('information_char_mapping_unavailable')
    ids = {s['source_block_id'] for s in selected}
    refs = [deepcopy(r) for r in unit['source_refs'] if char_range is None or r['block_id'] in ids]
    result = {'schema_version':'information-location-v1','data_id':packet['data_id'],
        'source_execution_id':packet['source_execution_id'],'input_sha256':packet['input_sha256'],
        'information_id':information_id,'char_range':char_range,'source_refs':refs,'content_segments':selected,
        'status':'source_refs_available' if refs else 'assembly_separator',
        'coordinate_precision':'retained_block_and_leaf_regions; not inferred per-character glyph boxes',
        'llm_calls':0,'canonical_writes':0}
    result['location_sha256'] = digest(result)
    return result


def lookup_source(packet, *, page_number=None, bbox=None, byte_range=None, line_range=None):
    """Return exact I/source refs, with visual fallback distinguished from OCR."""
    _full_packet(packet)
    modes = int(page_number is not None) + int(byte_range is not None) + int(line_range is not None)
    if modes != 1 or (bbox is not None and page_number is None):
        _fail('invalid_source_location')
    markdown = packet['model_input'].get('source_format') in ('markdown', 'code')
    if markdown == (page_number is not None):
        _fail('invalid_source_location')
    if page_number is not None:
        if type(page_number) is not int or not 1 <= page_number <= packet['page_count']:
            _fail('invalid_source_location')
        if bbox is not None and (not isinstance(bbox, (list,tuple)) or len(bbox) != 4
                or any(type(n) not in (int,float) or not math.isfinite(n) for n in bbox)
                or bbox[0] < 0 or bbox[1] < 0 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]):
            _fail('invalid_source_location')
    else:
        interval = byte_range if byte_range is not None else line_range
        minimum = 0 if byte_range is not None else 1
        if (not isinstance(interval, (list,tuple)) or len(interval) != 2
                or any(type(n) is not int for n in interval) or interval[0] < minimum
                or interval[1] < interval[0] or (byte_range is not None and interval[1] == interval[0])):
            _fail('invalid_source_location')
    matched, visual, parsed = [], [], []
    for unit in packet['model_input']['information']:
        refs = []
        for ref in unit['source_refs']:
            if page_number is not None:
                if ref['page_index'] != page_number-1:
                    continue
                if bbox is not None and (bbox[2] > ref['page_size'][0] or bbox[3] > ref['page_size'][1]):
                    _fail('invalid_source_location')
                rb = ref['bbox']
                if bbox is not None and not (max(bbox[0],rb[0]) < min(bbox[2],rb[2]) and
                                             max(bbox[1],rb[1]) < min(bbox[3],rb[3])):
                    continue
            else:
                span = ref['text_range']; field = 'byte' if byte_range is not None else 'line'
                start,end = span[field+'_start'],span[field+'_end']
                if not (max(interval[0],start) < min(interval[1],end) if field=='byte' else
                        max(interval[0],start) <= min(interval[1],end)):
                    continue
            refs.append(deepcopy(ref))
        if refs:
            ids = {r['block_id'] for r in refs}
            facade = any(r.get('source_collection') == PAGE_COLLECTION for r in refs)
            (visual if facade else parsed).append(unit['information_id'])
            matched.append({'information_id':unit['information_id'],'title':unit['title'],
                'kind':unit['kind'],'source_refs':refs,
                'content_segments':[deepcopy(s) for s in unit.get('source_assembly', {}).get('content_segments', [])
                                    if s['source_block_id'] in ids],
                'media':[deepcopy(m) for m in unit['media'] if m['source_block_id'] in ids],
                'match_basis':'original_page_facsimile' if facade else 'retained_source_region'})
    result = {'schema_version':'source-location-v1','data_id':packet['data_id'],
        'source_execution_id':packet['source_execution_id'],'input_sha256':packet['input_sha256'],
        'query':{'page_number':page_number,'bbox':bbox,'byte_range':byte_range,'line_range':line_range},
        'matches':matched,'parsed_information_ids':parsed,'page_image_information_ids':visual,
        'status':('visible_page_region_available' if visual else 'source_region_matched' if matched else 'unmapped_region'),
        'ocr_text_coverage_verified':False if not markdown else None,
        'original_page_region_available':bool(visual), 'llm_calls':0,'canonical_writes':0}
    result['location_sha256'] = digest(result)
    return result
