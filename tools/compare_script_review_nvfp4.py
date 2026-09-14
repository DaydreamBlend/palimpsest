"""Offline NVFP4 comparison using the unchanged, hash-bound 9B/4B evaluators."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import compare_script_review_models as paired

base = paired.base
require = base.old.require
MODEL = 'qwen35-9b-nvfp4'
PROTOCOL_SHA = 'a4b7d9101e0e3ee3c96e2a77ec88dbc9b7f9e23f34b60f08d9ac8b4300aa11f1'
LINEAGE_SHA = 'c78ce1d14ba8518ccc4acf4fde7a6729a227dbff467403c92295002134655708'
REFERENCES = {
    'qwen35-9b-q8': ('t03-script-context-review', paired.REFERENCE_METRICS),
    'qwen35-4b-q4': ('t03-script-context-review-4b', '7fce9546b8f3fd9581f62dc951356c3223fba6c46bb8705b7254682484739469'),
}
PAIRED_SHA = 'f9fbc4f5397b9fa9a613176e26931a2d79044e0377c390eb8ecf87b78d60f381'


def read(path, hashes, expected=None):
    known = hashes.get(str(Path(path).resolve()))
    require(known is None or expected is None or known == expected, 'conflicting_hash_binding')
    return paired.bound_read(path, hashes, expected if expected is not None else known)


def packet_run(root, packet, repeat, protocol, hashes):
    observed = {}
    result = base.read_packet_run(root, packet, repeat, protocol, observed)
    require(all(hashes.get(path, digest) == digest for path, digest in observed.items()),
            'previously_bound_packet_changed')
    hashes.update(observed)
    return result


def read_final(folder, packet_ids, hashes):
    present = [folder / name for name in ('projection.json', 'failure.json') if (folder / name).is_file()]
    require(len(present) == 1, 'missing_or_conflicting_final_receipts')
    if present[0].name == 'failure.json':
        failure = read(present[0], hashes)
        require(isinstance(failure, dict) and set(failure) == {'failed_packets'}
                and isinstance(failure['failed_packets'], list) and failure['failed_packets']
                and all(isinstance(i, str) and i in packet_ids for i in failure['failed_packets'])
                and len(set(failure['failed_packets'])) == len(failure['failed_packets']), 'invalid_failure_receipt')
        return None, None
    return read(folder / 'projection.json', hashes), read(folder / 'normalized.json', hashes)


def same_request(reference, candidate, reference_model):
    require(isinstance(reference, dict) and isinstance(candidate, dict), 'invalid_request')
    require(reference.get('model') == reference_model and candidate.get('model') == MODEL,
            'request_model_identity_mismatch')
    return base.old.digest({k: v for k, v in reference.items() if k != 'model'}) == base.old.digest(
        {k: v for k, v in candidate.items() if k != 'model'})


def load_context(root, repo):
    reference_root = repo / 'output' / REFERENCES['qwen35-9b-q8'][0]
    protocol, evaluation, source, draft, packets, oracle, hashes = base.load_inputs(reference_root, repo)
    references = {}
    for alias, (directory, expected) in REFERENCES.items():
        folder = repo / 'output' / directory
        metrics = read(folder / 'metrics.json', hashes, expected)
        require(metrics['model'] == alias and metrics['state'] == 'complete'
                and len(metrics['repeats']) == 3 and all(r['valid'] for r in metrics['repeats']),
                'invalid_reference_metrics:' + alias)
        for name, digest in metrics['input_file_sha256'].items():
            require(base.old.file_hash(name) == digest, 'reference_artifact_changed:' + name)
            require(hashes.get(name, digest) == digest, 'conflicting_reference_binding:' + name)
            hashes[name] = digest
        references[alias] = {'root': folder, 'metrics': metrics}
    for module, expected in ((base, paired.REFERENCE_SCORER), (paired, PAIRED_SHA)):
        require(base.old.file_hash(module.__file__) == expected, 'reused_evaluator_changed')
        hashes[str(Path(module.__file__).resolve())] = expected
    candidate = read(root / 'protocol.json', hashes, PROTOCOL_SHA)
    lineage = read(root / 'comparison-protocol.json', hashes, LINEAGE_SHA)
    require(candidate['model'] == lineage['model'] == MODEL
            and lineage['baseline_model'] == protocol['model']
            and lineage['baseline_protocol_sha256'] == base.SCRIPT_PROTOCOL
            and lineage['protocol_sha256'] == PROTOCOL_SHA
            and Path(lineage['baseline_root']).resolve() == reference_root.resolve(), 'candidate_identity_changed')
    require({k: v for k, v in candidate.items() if k not in ('model', 'frozen_hashes')}
            == {k: v for k, v in protocol.items() if k not in ('model', 'frozen_hashes')}, 'conditions_changed')
    require(candidate['repeats'] == 3 and len(packets) == 7, 'fixed_run_universe_changed')
    for name, expected in candidate['frozen_hashes'].items():
        path = root / 'frozen' / name
        require(base.old.file_hash(path) == expected, 'candidate_harness_changed:' + name)
        hashes[str(path.resolve())] = expected
    read_driver = root / 'frozen/run_script_review_comparison.py'
    require(base.old.file_hash(read_driver) == lineage['driver_sha256'], 'driver_changed')
    hashes[str(read_driver.resolve())] = lineage['driver_sha256']
    original = (reference_root / 'frozen/run_script_context_review.py').read_bytes()
    delta = lineage['transport_delta']
    require(original.count(delta['before'].encode()) == 1
            and original.replace(delta['before'].encode(), delta['after'].encode())
            == (root / 'frozen/run_script_context_review.py').read_bytes(), 'non_model_transport_change')
    original_copy = root / 'frozen/run_script_context_review.py.original'
    require(original_copy.read_bytes() == original, 'original_runner_copy_changed')
    hashes[str(original_copy.resolve())] = base.old.file_hash(original_copy)
    for name, expected in lineage['copied_artifact_sha256'].items():
        read(reference_root / name, hashes, expected)
        read(root / name, hashes, expected)
    return candidate, evaluation, source, draft, packets, oracle, hashes, references


def read_run(root, packet, repeat, protocol, hashes, references, *, control=False):
    directory = root / 'controls' if control else root
    row, value = packet_run(directory, packet, repeat, protocol, hashes)
    relative = Path('runs') / packet['packet_id'] / f'repeat-{repeat}' / 'request.json'
    row['request_matches'] = {}
    for alias, reference in references.items():
        try:
            previous_root = reference['root'] / 'controls' if control else reference['root']
            match = same_request(read(previous_root / relative, hashes), read(directory / relative, hashes), alias)
            row['request_matches'][alias] = match
            require(match, 'request_differs_beyond_model:' + alias)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row['valid'] = False
            row['request_matches'][alias] = False
            row['errors'].append(type(exc).__name__ + ':' + str(exc))
    return row, value if row['valid'] else None


def compare_projection(projected, quality, groups, previous, previous_quality, oracle, evaluation):
    _, old_groups = base.assess(base.normalized(previous), oracle, evaluation)
    result = paired.compare_ledgers(previous['ledger'], projected['ledger'])
    prior_probes = {p['id']: p['passed'] for p in previous_quality['probes']}
    result.update(partition_match=quality['partition_sha256'] == previous_quality['partition_sha256'],
        annotations_match=base.old.partition_hash(groups, annotated=True) == base.old.partition_hash(old_groups, annotated=True),
        figure_companions_match=base.old.digest(projected['figures']) == base.old.digest(previous['figures']),
        ledger_exact_match=base.old.digest(projected['ledger']) == base.old.digest(previous['ledger']),
        reference_primary_pairwise_f1=previous_quality['quality']['primary_pairwise']['f1'],
        primary_pairwise_f1_delta=quality['quality']['primary_pairwise']['f1'] - previous_quality['quality']['primary_pairwise']['f1'],
        newly_passed_probes=[p['id'] for p in quality['probes'] if p['passed'] and not prior_probes[p['id']]],
        newly_failed_probes=[p['id'] for p in quality['probes'] if not p['passed'] and prior_probes[p['id']]])
    return result


def evaluate(root, repo):
    protocol, evaluation, source, draft, packets, oracle, hashes, references = load_context(root, repo)
    draft_quality, draft_groups = base.assess(base.normalized(draft), oracle, evaluation)
    require(draft_quality['structural_valid'], 'invalid_frozen_draft')
    repeats = []
    for repeat in range(1, 4):
        runs, decisions = [], {}
        for packet in packets:
            run, value = read_run(root, packet, repeat, protocol, hashes, references)
            runs.append(run)
            if run['valid']:
                decisions[packet['packet_id']] = value
        folder = root / 'final' / f'repeat-{repeat}'
        row = {'repeat': repeat, 'packet_runs': runs, 'observed_final': False,
               'valid': False, 'errors': [], 'quality_after': None, 'comparisons': {}}
        try:
            actual, converted = read_final(folder, {p['packet_id'] for p in packets}, hashes)
            row['observed_final'] = True
            require(all(r['valid'] for r in runs), 'invalid_or_missing_packet_results')
            require(actual is not None, 'runner_failure_receipt')
            projected = base.replay(draft, packets, decisions, source['items'])
            require(base.old.digest(actual) == base.old.digest(projected)
                    and base.old.digest(converted) == base.old.digest(base.normalized(projected)), 'final_replay_mismatch')
            quality, groups = base.assess(converted, oracle, evaluation)
            require(quality['structural_valid'], 'invalid_final_partition')
            for alias, previous in references.items():
                reference_row = previous['metrics']['repeats'][repeat - 1]
                require(reference_row['repeat'] == repeat, 'reference_repeat_mismatch')
                reference_projection = read(previous['root'] / 'final' / f'repeat-{repeat}' / 'projection.json', hashes)
                row['comparisons'][alias] = compare_projection(projected, quality, groups,
                    reference_projection, reference_row['quality_after'], oracle, evaluation)
            row.update(valid=True, quality_after=quality, unresolved=projected['unresolved'],
                review_complete=not projected['unresolved'], ledger=projected['ledger'],
                reason_code_diagnostics=base.reason_diagnostics(packets, decisions),
                delta_from_draft=base.compare(draft_groups, groups, oracle))
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            row['errors'].append(type(exc).__name__ + ':' + str(exc))
        repeats.append(row)
    reference_root = references['qwen35-9b-q8']['root']
    control_protocol = read(reference_root / 'controls/protocol.json', hashes, paired.REFERENCE_CONTROL)
    packet = read(root / 'controls/packet.json', hashes, control_protocol['packet_sha256'])
    expected = read(root / 'controls/expected.json', hashes, control_protocol['expected_sha256'])
    control_run, control_value = read_run(root, packet, 1, protocol, hashes, references, control=True)
    control = {'run': control_run, 'valid': control_run['valid'], 'reference_results': {},
        'checks': [{'issue': key, 'expected': choice,
            'observed': control_value[key]['decision'] if control_run['valid'] else None,
            'passed': control_value[key]['decision'] == choice if control_run['valid'] else None} for key, choice in expected.items()],
        'decisions': control_value, 'faults': 2, 'repeats': 1, 'excluded_from_main_metrics': True,
        'scope': 'Same two post-hoc faults, known from prior runs; no held-out success-rate claim.'}
    for alias, previous in references.items():
        old_run, old_value = packet_run(previous['root'] / 'controls', packet, 1,
            dict(protocol, model=alias), hashes)
        require(old_run['valid'], 'invalid_reference_control:' + alias)
        control['reference_results'][alias] = {'run': old_run, 'decisions': old_value,
            'passed_faults': sum(old_value[key]['decision'] == choice for key, choice in expected.items())}
    control['passed_faults'] = sum(item['passed'] for item in control['checks']) if control_run['valid'] else None
    runs = [r for repeat in repeats for r in repeat['packet_runs']]
    valid = [r for r in repeats if r['valid']]
    report = {'schema_version': 'script-review-nvfp4-comparison-v1', 'model': MODEL,
        'state': 'complete' if control_run['result_present'] and all(r['observed_final'] for r in repeats)
                 and all(r['result_present'] for r in runs) else 'partial',
        'draft': draft_quality, 'repeats': repeats, 'control': control,
        'summary': {'expected_model_calls': 21, 'observed_model_calls': sum(r['response_present'] for r in runs),
            'valid_model_calls': sum(r['valid'] for r in runs), 'valid_repeats': len(valid),
            'review_complete_repeats': sum(r['review_complete'] for r in valid),
            'unique_valid_partitions': len({r['quality_after']['partition_sha256'] for r in valid}),
            'all_requests_same_except_model': all(all(r['request_matches'].values()) for r in runs),
            'comparisons': {alias: {
                **{key + '_repeats': sum(r['comparisons'][alias][key] for r in valid) for key in
                   ('partition_match', 'annotations_match', 'figure_companions_match', 'ledger_exact_match')},
                **{key: sum(r['comparisons'][alias][key] for r in valid) for key in
                   ('issues', 'decision_match_count', 'evidence_set_match_count', 'evidence_order_match_count', 'reason_code_match_count')}}
                for alias in references}},
        'usage_and_timing': {MODEL: paired.usage_summary(runs), **{alias: paired.usage_summary(
            [run for repeat in previous['metrics']['repeats'] for run in repeat['packet_runs']]) for alias, previous in references.items()}},
        'limitations': ['One known paper,20 fixed issues,3 repeats,text-only; no OCR/image/K-generation evaluation.',
            'Figure1 reference packing and post-hoc reason-code rubric are unchanged; packing agreement is not semantic truth.',
            'Formal validity, needs_context obligations and two-fault semantic outcomes are distinct.',
            'Packet times/usage include preflight; exclude model loading, inter-call waits, smoke and control.',
            'Different quantization, tokenizer/template and external GPU load prevent model-size-only timing claims.',
            'Physical model/tensor/GPU/runtime evidence is audited separately, not asserted by this offline scorer.'],
        'scorer_model_calls': 0, 'scorer_database_calls': 0, 'scorer_existing_source_writes': 0}
    return report, hashes


def markdown(report):
    lines = ['# 같은 스크립트 초안의 NVFP4 비교', '',
        f"정식 21회 중 구조상 유효한 결과는 {report['summary']['valid_model_calls']}개입니다. 구조 유효성과 의미적 오류 탐지를 구분합니다.", '',
        '| 반복 | 유효 | 그룹 수 | Primary F1 | 미해결 | 9B Q8과 같은 구성 | 4B Q4와 같은 구성 |',
        '|---|---|---:|---:|---|---|---|']
    for row in report['repeats']:
        if row['valid']:
            quality = row['quality_after']
            lines.append(f"|{row['repeat']}|예|{quality['groups_count']}|{quality['quality']['primary_pairwise']['f1']:.6f}|{row['unresolved']}|"
                         f"{row['comparisons']['qwen35-9b-q8']['partition_match']}|{row['comparisons']['qwen35-4b-q4']['partition_match']}|")
        else:
            lines.append(f"|{row['repeat']}|아니오|—|—|—|—|—|")
    for alias, summary in report['summary']['comparisons'].items():
        lines += ['', f"{alias} 대비 {summary['issues']}개 결정 중 선택 {summary['decision_match_count']}개, 근거 집합 {summary['evidence_set_match_count']}개, "
            f"근거 순서 {summary['evidence_order_match_count']}개, 이유 코드 {summary['reason_code_match_count']}개가 같습니다."]
    control = report['control']
    control_score = f"{control['passed_faults']}/2" if control['valid'] else '평가 불가'
    lines += ['', f"별도 두 오류 대조의 구조 유효성은 {control['valid']}이며, 기대 선택 일치는 {control_score}입니다."]
    for alias, value in control['reference_results'].items():
        lines.append(f"기존 {alias}: {value['passed_faults']}/2. 이 두 사례를 일반 성공률로 해석하거나 정식 21회 점수에 합산하지 않습니다.")
    lines += ['', '동일 문서의 원문·후보·policy·schema·요청 설정을 고정하고 model만 바꾸었습니다. Figure 1의 두 실제 소절과 수동 packing의 차이는 의미 오류 수가 아닙니다.', '',
        '전사 충실도·이미지 이해·K 생성·다른 논문 일반화는 평가하지 않았습니다. 이유 코드 호환성은 기존 사후 진단이며 구조 유효성을 바꾸지 않습니다.', '',
        '토큰·시간 관측값, 세 반복의 primary F1/probe, 원문·Figure companion·선택·근거·이유 차이와 실패 진단은 metrics.json에 있습니다. 양자화·runtime·외부 GPU 부하 차이는 별도 물리 감사와 함께 해석해야 합니다.', '']
    return '\n'.join(lines)


def publish(root, report, hashes):
    require(report['state'] == 'complete', 'incomplete_runs_no_metrics_written')
    targets = (root / 'metrics.json', root / 'EVALUATION.md')
    require(not any(path.exists() for path in targets), 'evaluation_output_already_exists')
    require(all(base.old.file_hash(path) == expected for path, expected in hashes.items()), 'input_changed_during_evaluation')
    report.update(input_file_sha256=hashes, comparator_sha256=base.old.file_hash(__file__))
    # Render both before writing; publish complete metrics last. Partial output
    # remains exclusive and must not be treated as a successful publication.
    contents = ((targets[1], markdown(report)),
                (targets[0], json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'))
    for path, content in contents:
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(content)


def self_check():
    left = {'model': 'qwen35-9b-q8', 'messages': [{'role': 'user', 'content': 'source'}], 'temperature': 0}
    right = dict(deepcopy(left), model=MODEL)
    assert same_request(left, right, left['model'])
    right['messages'][0]['content'] = 'tampered'
    assert not same_request(left, right, left['model'])
    ledger = [{'issue': 'x', 'decision': 'keep', 'evidence_ids': [1, 2], 'reason_code': 'source_structure'}]
    reordered = deepcopy(ledger)
    reordered[0]['evidence_ids'].reverse()
    result = paired.compare_ledgers(ledger, reordered)
    assert result['evidence_set_match_count'] == 1 and result['evidence_order_match_count'] == 0
    with TemporaryDirectory(prefix='nvfp4-scorer-') as temporary:
        root = Path(temporary)
        file = root / 'bound.json'
        file.write_text('{"value":1}', encoding='utf-8')
        hashes = {}
        read(file, hashes)
        file.write_text('{"value":2}', encoding='utf-8')
        final = root / 'final'
        final.mkdir()
        (final / 'projection.json').write_text('{}', encoding='utf-8')
        for action in (lambda: read(file, hashes), lambda: publish(root, {'state': 'partial'}, {}),
                       lambda: read_final(final, {'p'}, {})):
            try:
                action()
            except (ValueError, OSError):
                pass
            else:
                raise AssertionError('tampering_or_partial_run_not_rejected')
        (final / 'normalized.json').write_text('{', encoding='utf-8')
        try:
            read_final(final, {'p'}, {})
        except ValueError:
            pass
        else:
            raise AssertionError('truncated_final_not_rejected')
        failed = root / 'failed'
        failed.mkdir()
        (failed / 'failure.json').write_text('{"failed_packets":["p"]}', encoding='utf-8')
        assert read_final(failed, {'p'}, {}) == (None, None)
        assert not (root / 'metrics.json').exists() and not (root / 'EVALUATION.md').exists()
    print(json.dumps({'self_check': 'passed', 'checks': 6, 'model_calls': 0, 'database_calls': 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('output/t03-script-context-review-nvfp4'))
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    root, repo = args.root.resolve(strict=True), args.repo.resolve(strict=True)
    report, hashes = evaluate(root, repo)
    publish(root, report, hashes)
    print(json.dumps({'state': report['state'], **report['summary'], 'control_passed_faults': report['control']['passed_faults']}))


if __name__ == '__main__':
    main()
