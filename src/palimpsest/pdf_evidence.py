"""Build and read immutable PDF evidence projections beside retained parser runs."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil

from .errors import PalimpsestError
from .mineru_adapter import normalize_middle
from .paragraph_projection import build_paragraphs, digest, select_evidence_context


PRO_REVISION = 'bff20d4ae2bf202df9f45284b4d43681555a97ed'
PRO_WEIGHT = 'abf8681ca63b8dec7b67de257af47b821f179442f72998d0696ae2ed9232a5f0'
DUAL_ADAPTER = 'mineru-hybrid-dual200-v1'
IMAGE_ADAPTER = 'mineru-hybrid-image200-v1'
RETAINED_ADAPTERS = (DUAL_ADAPTER, IMAGE_ADAPTER)


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def file_hash(path):
    with Path(path).open('rb') as stream:
        return sha256(stream.read()).hexdigest()


def local_file(root, relative):
    if (not isinstance(relative, str) or not relative or any(c in relative for c in ('\\', ':', '\x00'))
            or PurePosixPath(relative).is_absolute()
            or any(part in ('', '.', '..') for part in relative.split('/'))):
        raise PalimpsestError('unsafe_evidence_path', '근거 파일의 상대 경로를 확인하세요.', 4)
    path = root
    for part in relative.split('/'):
        path = path / part
        if path.is_symlink():
            raise PalimpsestError('unsafe_evidence_path', '근거 파일의 symlink는 허용하지 않습니다.', 4)
    if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)) or not path.is_file():
        raise PalimpsestError('unsafe_evidence_path', '근거 파일이 없습니다.', 4)
    return path


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def publish_manifest(directory, manifest):
    """The atomically published manifest is the only v2 completion marker."""
    temporary = directory / '.manifest.partial.json'
    write_json(temporary, manifest)
    with temporary.open('r+b') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, directory / 'manifest.json')


def verify_parse_result(path, pdf_path):
    receipt = read_json(path)
    if (receipt.get('status') != 'complete' or receipt.get('backend') != 'hybrid-engine'
            or receipt.get('effort') != 'high' or receipt.get('resolved_engine') != 'transformers'
            or receipt.get('versions', {}).get('mineru') != '3.4.5'
            or receipt.get('pro_revision') != PRO_REVISION or receipt.get('pro_weight_sha256') != PRO_WEIGHT
            or receipt.get('network') != 'none'):
        raise PalimpsestError('evidence_profile_mismatch', '선택한 MinerU Hybrid + Pro 실행 기록이 필요합니다.', 4)
    data_id = file_hash(pdf_path)
    if any(receipt.get(key) != data_id for key in ('data_id', 'source_sha256_before', 'source_sha256_after')):
        raise PalimpsestError('evidence_source_changed', '원본 PDF와 파싱 실행의 hash가 다릅니다.', 4)
    records = receipt.get('artifacts', [])
    if not records or len({r['path'] for r in records}) != len(records):
        raise PalimpsestError('evidence_manifest_invalid', '실행 산출물 목록을 확인하세요.', 4)
    for record in records:
        artifact = local_file(path.parent, record['path'])
        if artifact.stat().st_size != record['bytes'] or file_hash(artifact) != record['sha256']:
            raise PalimpsestError('evidence_artifact_changed', '보존된 파서 산출물이 변경됐습니다.', 4)
    if receipt['middle_relative_path'] not in {r['path'] for r in records}:
        raise PalimpsestError('evidence_manifest_invalid', 'middle JSON이 실행 manifest에 없습니다.', 4)
    return receipt


def _normalize_evidence_bundle(middle_path, receipt, receipt_hash):
    middle = read_json(middle_path)
    if receipt.get('adapter_version') in RETAINED_ADAPTERS:
        from .dual_adapter import normalize_dual
        from .image_adapter import normalize_image
        from .hybrid_receipt import validate_hybrid_receipt

        retained = read_json(local_file(middle_path.parent, 'palimpsest_source_check.json'))
        profile = read_json(local_file(middle_path.parent, 'palimpsest_profile.json'))
        if retained != receipt:
            raise PalimpsestError('evidence_source_changed', '보존된 두 실행 기록이 다릅니다.', 4)
        validate_hybrid_receipt(retained, profile=profile, data_id=receipt['data_id'],
                                middle_name=middle_path.name, expected_pages=receipt['page_count'])
        # The canonical adapter receives this exact parser profile. The outer
        # receipt hash belongs to the export manifest, not the source bundle.
        normalize = normalize_image if receipt['adapter_version'] == IMAGE_ADAPTER else normalize_dual
        return normalize(middle, data_id=receipt['data_id'], artifact_root=middle_path.parent,
                         expected_pages=receipt['page_count'], profile=profile['parser'], receipt=retained)
    profile = {'provider': 'mineru', 'version': '3.4.5', 'backend': 'hybrid-engine',
               'adapter_version': 'mineru-hybrid-preproc-v1', 'effort': 'high',
               'resolved_engine': 'transformers', 'parse_result_sha256': receipt_hash,
               'pro_revision': PRO_REVISION, 'pro_weight_sha256': PRO_WEIGHT}
    return normalize_middle(middle, data_id=receipt['data_id'], artifact_root=middle_path.parent,
                            expected_pages=receipt['page_count'], profile=profile)


def _copy_dual_raw(parse_result, middle_path, receipt, output_dir):
    """Keep complete SDK trees, original pixels and runtime receipts."""
    raw_root = output_dir / 'parser_raw'
    raw_root.mkdir()
    names = [r['path'] for r in receipt['artifacts']]
    # The source check is written after the artifact inventory, deliberately
    # outside its own hash list. It has exactly the outer receipt's content.
    names.append((middle_path.parent / 'palimpsest_source_check.json').relative_to(parse_result.parent).as_posix())
    for name in sorted(set(names)):
        source = local_file(parse_result.parent, name)
        target = raw_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(parse_result, raw_root / 'parse_result.json')
    return {'adapter_version': receipt['adapter_version'], 'parse_result_path': 'parser_raw/parse_result.json',
            'source_check_path': 'parser_raw/' + names[-1],
            'parser_artifact_directory': 'parser_raw/' + PurePosixPath(receipt['middle_relative_path']).parent.as_posix(),
            'transcription_selection_sha256': None}


def create_pdf_evidence(parse_result, output_dir, *, pdf_path=None):
    """No DB writes or model calls: derive sidecars from a verified parser run."""
    from .pdf_text_evidence import extract_pdf_text, analyze_pdf_text
    from .pdf_visual_evidence import build_pdf_visuals

    implementations = {name: file_hash(Path(__file__).parent / name) for name in
        ('pdf_evidence.py', 'pdf_text_evidence.py', 'pdf_visual_evidence.py', 'paragraph_projection.py', 'mineru_adapter.py',
         'dual_adapter.py', 'hybrid_receipt.py', 'hybrid_profile.py', 'pdf_raster.py', 'pdf_raster_adapter.py',
         'transcription_selection.py', 'image_adapter.py')}

    parse_result = Path(parse_result).resolve(strict=True)
    receipt = read_json(parse_result)
    pdf_path = (Path(pdf_path).resolve(strict=True) if pdf_path else
                local_file(parse_result.parent, receipt['source_relative_path']))
    output_dir = Path(output_dir).resolve()
    if (output_dir.exists() or output_dir.is_relative_to(parse_result.parent)
            or parse_result.is_relative_to(output_dir)):
        raise PalimpsestError('evidence_output_exists', '새 근거 출력 디렉터리를 지정하세요.', 6)
    receipt_hash = file_hash(parse_result)
    receipt = verify_parse_result(parse_result, pdf_path)
    middle_path = local_file(parse_result.parent, receipt['middle_relative_path'])
    middle = read_json(middle_path)
    bundle = _normalize_evidence_bundle(middle_path, receipt, receipt_hash)
    if bundle['block_collection'] != 'preproc_blocks' or bundle['unsupported_block_ids']:
        raise PalimpsestError('unsupported_source_structure', '모든 원문 preproc block을 확인해야 합니다.', 4)
    native = extract_pdf_text(pdf_path, data_id=receipt['data_id'])
    comparison_bundle = bundle
    if receipt.get('adapter_version') == DUAL_ADAPTER:
        comparison_bundle = {**bundle, 'blocks': [{**b, 'text': b['native_text']} for b in bundle['blocks']]}
    analysis = analyze_pdf_text(native, comparison_bundle)
    if comparison_bundle is not bundle:
        analysis['compared_transcription'] = 'native_parser_raw'
    paragraphs = build_paragraphs(middle, bundle)
    output_dir.mkdir(parents=True)
    write_json(output_dir / 'status.json', {'state': 'building', 'canonical_writes': 0})
    visuals = build_pdf_visuals(pdf_path, bundle, output_dir / 'visuals', artifact_root=middle_path.parent)
    dual = None
    if receipt.get('adapter_version') in RETAINED_ADAPTERS:
        dual = _copy_dual_raw(parse_result, middle_path, receipt, output_dir)
        if receipt['adapter_version'] == DUAL_ADAPTER:
            dual['transcription_selection_sha256'] = digest(bundle['transcription_selection'])
        else:
            dual.pop('transcription_selection_sha256')
            dual['raster_manifest_sha256'] = bundle['raster_manifest_sha256']
        copied_receipt = local_file(output_dir, dual['parse_result_path'])
        verify_parse_result(copied_receipt, output_dir / 'parser_raw' / receipt['source_relative_path'])
        copied_middle = local_file(copied_receipt.parent, receipt['middle_relative_path'])
        if digest(_normalize_evidence_bundle(copied_middle, receipt, receipt_hash)) != digest(bundle):
            raise PalimpsestError('evidence_artifact_changed', '복사한 두 전사 근거를 재현할 수 없습니다.', 4)
    for name, source in (('source.pdf', pdf_path), ('source_middle.json', middle_path), ('parse_result.json', parse_result)):
        shutil.copyfile(source, output_dir / name)
    for name, content in (('source_bundle.json', bundle), ('pdf_native_text.json', native),
                          ('text_analysis.json', analysis), ('paragraphs.json', paragraphs)):
        write_json(output_dir / name, content)
    lines = ['# PDF 원문 근거', '', '이 자료는 원문과 조회용 후보입니다. 의미 검증이나 자동 교정 결과가 아닙니다.', '',
             f"- Data SHA-256: `{receipt['data_id']}`", f"- 페이지: {receipt['page_count']}",
             f"- 소제목 후보: {len(analysis['heading_candidates'])}",
             f"- 전사 불일치/검토 항목: {len(analysis['discrepancies'])}", '',
             '[원본 PDF](source.pdf) · [문단과 원래 페이지 매핑](paragraphs.json) · [후보/불일치](text_analysis.json)', '']
    for page in visuals['pages']:
        image = page['page_image']
        lines.extend([f"## Page {page['page_index'] + 1}", '', f"![원본 페이지](visuals/{image['path']})", ''])
    (output_dir / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    # Verify the input snapshot again before publishing the complete marker.
    verify_parse_result(parse_result, pdf_path)
    if file_hash(parse_result) != receipt_hash:
        raise PalimpsestError('evidence_artifact_changed', '실행 기록이 처리 중 변경됐습니다.', 4)
    if any(file_hash(Path(__file__).parent / name) != expected for name, expected in implementations.items()):
        raise PalimpsestError('evidence_implementation_changed', '처리 중 실행 코드가 변경됐습니다.', 4)
    write_json(output_dir / 'status.json', {'state': 'artifacts_verified', 'canonical_writes': 0,
        'semantic_llm_calls': 0, 'fidelity': 'requires_review', 'known_parser_errors_repaired': False})
    files = [{'path': p.relative_to(output_dir).as_posix(), 'sha256': file_hash(p), 'bytes': p.stat().st_size}
             for p in sorted(output_dir.rglob('*')) if p.is_file()]
    manifest = {'schema_version': 'pdf-evidence-v2', 'state': 'complete', 'data_id': receipt['data_id'],
        'parse_result_sha256': receipt_hash, 'source_bundle_sha256': digest(bundle),
        'implementation_sha256': implementations,
        'files': files, 'page_count': receipt['page_count'], 'canonical_writes': 0,
        'semantic_llm_calls': 0, 'figure_regions_are_proposals': True}
    if dual:
        key = 'image_transcription' if receipt['adapter_version'] == IMAGE_ADAPTER else 'dual_transcription'
        manifest[key] = dual
    publish_manifest(output_dir, manifest)
    return {'state': 'complete', 'directory': str(output_dir), 'data_id': receipt['data_id'],
            'manifest_sha256': file_hash(output_dir / 'manifest.json'), 'pages': receipt['page_count'],
            'heading_candidates': len(analysis['heading_candidates']), 'discrepancies': len(analysis['discrepancies']),
            'figures': len(visuals['figures']), 'canonical_writes': 0, 'semantic_llm_calls': 0}


def read_evidence(directory):
    directory = Path(directory).resolve(strict=True)
    manifest_file = local_file(directory, 'manifest.json')
    manifest = read_json(manifest_file)
    if manifest.get('schema_version') not in ('pdf-evidence-v1', 'pdf-evidence-v2'):
        raise PalimpsestError('invalid_evidence_manifest', '지원하는 근거 manifest가 아닙니다.', 4)
    version2 = manifest['schema_version'] == 'pdf-evidence-v2'
    if version2 and manifest.get('state') != 'complete':
        raise PalimpsestError('evidence_incomplete', '근거 생성이 완료되지 않았습니다.', 4)
    names = {x['path'] for x in manifest['files']}
    required = {'source_bundle.json', 'text_analysis.json', 'paragraphs.json', 'visuals/manifest.json',
                'status.json', 'source.pdf', 'source_middle.json', 'pdf_native_text.json', 'parse_result.json'}
    if not required <= names or len(names) != len(manifest['files']):
        raise PalimpsestError('invalid_evidence_manifest', '필수 근거 파일이 빠졌습니다.', 4)
    for record in manifest['files']:
        path = local_file(directory, record['path'])
        if path.stat().st_size != record['bytes'] or file_hash(path) != record['sha256']:
            raise PalimpsestError('evidence_artifact_changed', '근거 파일의 hash를 확인하세요.', 4)
    if read_json(directory / 'status.json').get('state') != ('artifacts_verified' if version2 else 'complete'):
        raise PalimpsestError('evidence_incomplete', '근거 생성이 완료되지 않았습니다.', 4)
    result = {name: read_json(directory / filename) for name, filename in
              (('source_bundle', 'source_bundle.json'), ('text_analysis', 'text_analysis.json'),
               ('paragraphs', 'paragraphs.json'), ('visuals', 'visuals/manifest.json'))}
    bundle_hash = digest(result['source_bundle'])
    middle_hash = digest(read_json(directory / 'source_middle.json'))
    native = read_json(directory / 'pdf_native_text.json')
    receipt = read_json(directory / 'parse_result.json')
    adapter = result['source_bundle'].get('profile', {}).get('adapter_version')
    receipt_adapter = receipt.get('adapter_version')
    retained_modes = {'dual_transcription': DUAL_ADAPTER, 'image_transcription': IMAGE_ADAPTER}
    declared_modes = {key for key in retained_modes if key in manifest}
    if (adapter in RETAINED_ADAPTERS or receipt_adapter in RETAINED_ADAPTERS or declared_modes):
        expected_modes = {key for key, value in retained_modes.items() if value == adapter}
        if (adapter not in RETAINED_ADAPTERS or adapter != receipt_adapter
                or declared_modes != expected_modes):
            raise PalimpsestError('evidence_source_changed', '원문 전사 profile과 보존 manifest가 다릅니다.', 4)
    is_dual = adapter == DUAL_ADAPTER
    is_image = adapter == IMAGE_ADAPTER
    middle_records = [r for r in receipt.get('artifacts', [])
                      if r.get('path') == receipt.get('middle_relative_path')]
    if (result['source_bundle']['data_id'] != manifest['data_id']
            or bundle_hash != manifest['source_bundle_sha256']
            or file_hash(directory / 'source.pdf') != manifest['data_id']
            or file_hash(directory / 'parse_result.json') != manifest['parse_result_sha256']
            or any(receipt.get(key) != manifest['data_id'] for key in
                   ('data_id', 'source_sha256_before', 'source_sha256_after'))
            or (not (is_dual or is_image) and result['source_bundle'].get('profile', {}).get('parse_result_sha256') != manifest['parse_result_sha256'])
            or len(middle_records) != 1
            or middle_records[0].get('sha256') != file_hash(directory / 'source_middle.json')
            or middle_records[0].get('bytes') != (directory / 'source_middle.json').stat().st_size
            or native.get('data_id') != manifest['data_id']
            or result['text_analysis'].get('data_id') != manifest['data_id']
            or result['paragraphs'].get('data_id') != manifest['data_id']
            or result['paragraphs'].get('source_bundle_sha256') != bundle_hash
            or result['paragraphs'].get('source_middle_sha256') != middle_hash
            or result['visuals'].get('source', {}).get('data_id') != manifest['data_id']
            or result['visuals'].get('source', {}).get('pdf_sha256') != manifest['data_id']
            or result['visuals'].get('source', {}).get('bundle_sha256') != bundle_hash):
        raise PalimpsestError('evidence_source_changed', '원문 bundle이 일치하지 않습니다.', 4)
    if is_dual or is_image:
        adapter = IMAGE_ADAPTER if is_image else DUAL_ADAPTER
        dual = manifest.get('image_transcription' if is_image else 'dual_transcription', {})
        if (not version2 or dual.get('adapter_version') != adapter
                or receipt.get('adapter_version') != adapter
                or dual.get('parse_result_path') != 'parser_raw/parse_result.json'
                or (is_dual and dual.get('transcription_selection_sha256') != digest(result['source_bundle']['transcription_selection']))
                or (is_image and dual.get('raster_manifest_sha256') != result['source_bundle'].get('raster_manifest_sha256'))):
            raise PalimpsestError('evidence_source_changed', '원문 전사의 보존 manifest를 확인하세요.', 4)
        raw_receipt = local_file(directory, dual['parse_result_path'])
        if file_hash(raw_receipt) != manifest['parse_result_sha256']:
            raise PalimpsestError('evidence_source_changed', '복사된 실행 기록이 다릅니다.', 4)
        verify_parse_result(raw_receipt, directory / 'source.pdf')
        raw_middle = local_file(raw_receipt.parent, receipt['middle_relative_path'])
        expected_root = raw_middle.parent.relative_to(directory).as_posix()
        expected_check = expected_root + '/palimpsest_source_check.json'
        if (dual.get('parser_artifact_directory') != expected_root or dual.get('source_check_path') != expected_check
                or not {dual['parse_result_path'], expected_check} <= names
                or not {f'parser_raw/{r["path"]}' for r in receipt['artifacts']} <= names
                or digest(_normalize_evidence_bundle(raw_middle, receipt, manifest['parse_result_sha256'])) != bundle_hash
                or digest(build_paragraphs(read_json(raw_middle), result['source_bundle'])) != digest(result['paragraphs'])):
            raise PalimpsestError('evidence_source_changed', '보존된 원문 전사로 조회 결과를 재현할 수 없습니다.', 4)
        result['parser_artifact_base_directory'] = str(raw_middle.parent)
    result.update(manifest_sha256=file_hash(manifest_file), asset_base_directory=str(directory / 'visuals'))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    build = sub.add_parser('build')
    build.add_argument('--parse-result', type=Path, required=True)
    build.add_argument('--pdf', type=Path)
    build.add_argument('--output', type=Path, required=True)
    context = sub.add_parser('context')
    context.add_argument('--directory', type=Path, required=True)
    context.add_argument('--page', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        result = (create_pdf_evidence(args.parse_result, args.output, pdf_path=args.pdf) if args.action == 'build'
                  else select_evidence_context(read_evidence(args.directory), args.page))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (PalimpsestError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({'state': 'failed', 'error': getattr(exc, 'code', 'invalid_evidence_input')}))
        return getattr(exc, 'exit_code', 4)


if __name__ == '__main__':
    raise SystemExit(main())
