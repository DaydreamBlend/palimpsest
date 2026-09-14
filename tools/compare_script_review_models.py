"""Offline comparison of 4B and 9B on the same frozen script-review packets.

Reuses the 9B evaluator's validation and scoring functions without changing its
files or globals. Main runs and the separate two-fault control remain distinct.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics

import score_script_context_review as base

MODEL = 'qwen35-4b-q4'
REFERENCE_METRICS = '50f7bdf20cea9aeeb44cf19aaa0f48009c6be07f963b7b5c20439afa4a156960'
REFERENCE_SCORER = '7ec74ab67287dc741d91d842bab18f137203a96272ece3de80c735e0737f9454'
CANDIDATE_PROTOCOL = '6ddb59fb6ea684c854d46f5f2745fd3d9ed1a119038f525b8c2773eaf19c799a'
COMPARISON_PROTOCOL = '5df0a96f37144906fdde013af25fb7ed73792ce13c630686560d8e99ca2e5c9f'
REFERENCE_CONTROL = 'c328aa62dc111557f6602fc4d7b65a26c102570e019e1e890cfe1f73aa35948c'


def bound_read(path, hashes, expected=None):
    actual = base.old.file_hash(path)
    base.old.require(expected is None or actual == expected, 'bound_artifact_changed:' + str(path))
    hashes[str(path.resolve())] = actual
    return base.old.read(path)


def compare_requests(left, right):
    """The logical model label is the only permitted request difference."""
    base.old.require(isinstance(left, dict) and isinstance(right, dict), 'invalid_request')
    base.old.require(left.get('model') == 'qwen35-9b-q8' and right.get('model') == MODEL, 'model_identity_mismatch')
    return base.old.digest({k: v for k, v in left.items() if k != 'model'}) == base.old.digest(
        {k: v for k, v in right.items() if k != 'model'})


def compare_ledgers(reference, candidate):
    left, right = ({r['issue']: r for r in ledger} for ledger in (reference, candidate))
    base.old.require(len(left) == len(reference) and len(right) == len(candidate) and left.keys() == right.keys(),
                     'ledger_issue_coverage_mismatch')
    rows = []
    for issue, row in left.items():
        other = right[issue]
        rows.append({'issue': issue, 'decision_match': row['decision'] == other['decision'],
            'evidence_set_match': set(row['evidence_ids']) == set(other['evidence_ids']),
            'evidence_order_match': row['evidence_ids'] == other['evidence_ids'],
            'reason_code_match': row['reason_code'] == other['reason_code'],
            'reference': {k: row[k] for k in ('decision', 'evidence_ids', 'reason_code')},
            'candidate': {k: other[k] for k in ('decision', 'evidence_ids', 'reason_code')}})
    return {'issues': len(rows), **{key + '_count': sum(r[key] for r in rows) for key in
            ('decision_match', 'evidence_set_match', 'evidence_order_match', 'reason_code_match')}, 'rows': rows}


def usage_summary(runs):
    output = {}
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        values = [r['usage'][key] for r in runs if isinstance(r.get('usage'), dict)
                  and type(r['usage'].get(key)) is int]
        output[key] = {'observed_calls': len(values), 'sum': sum(values) if values else None}
    seconds = [r['seconds'] for r in runs if r['seconds'] is not None]
    output.update(seconds_observed_calls=len(seconds), seconds_sum=sum(seconds),
                  seconds_median=statistics.median(seconds) if seconds else None)
    return output


def runtime_metadata(root, reference_root, hashes):
    profiles = {}
    for directory, alias, quantization, expected_sha in (
        (root, MODEL, 'Q4_0', '298fcb5fe7a77ccc79745ae24751560c5ac56874caff4bb39b1f2055bd72b8bb'),
        (reference_root, 'qwen35-9b-q8', 'Q8_0', '809626574d0cb43d4becfa56169980da2bb448f2299270f7be443cb89d0a6ae4')):
        receipt = bound_read(directory / 'runtime/source-model-before.json', hashes)
        argv = bound_read(directory / 'server-command.json', hashes)
        props = bound_read(directory / 'runs/props.json', hashes)
        model = receipt['model']
        model_file = Path(model['file'])
        model_path = '/models/' + model_file.name
        base.old.require(model['verified'] is True and model['sha256'] == expected_sha
            and props['model_alias'] == alias and props['model_path'] == model_path
            and props['model_ftype'] == quantization and props['total_slots'] == 1
            and props['default_generation_settings']['n_ctx'] == 32768, 'loaded_model_receipt_mismatch')
        base.old.require(argv[argv.index('--model') + 1] == model_path and argv[argv.index('--alias') + 1] == alias,
                         'launch_model_mismatch')
        mounts = [argv[i + 1] for i, value in enumerate(argv[:-1]) if value == '--volume']
        base.old.require(any(m.endswith(':/models:ro') and Path(m[:-len(':/models:ro')]).resolve()
            == model_file.parent.resolve() for m in mounts), 'model_mount_not_receipt_readonly_path')
        settings, i = [], 0
        while i < len(argv):
            if argv[i] in ('--name', '--label', '--volume', '--model', '--alias'):
                i += 2
            else:
                settings.append(argv[i])
                i += 1
        profiles[alias] = {'model': model, 'model_path': model_path, 'quantization': quantization,
            'server_build': props['build_info'], 'non_model_launch_settings': settings,
            'gpu_start_snapshot_comparison': receipt.get('gpu_comparison')}
    return {'profiles': profiles,
        'non_model_server_settings_match': profiles[MODEL]['non_model_launch_settings'] == profiles['qwen35-9b-q8']['non_model_launch_settings'],
        'verification_scope': 'Binds saved pre-run full model-hash verification, actual launch model/read-only mount, and server props. Comparator does not rehash multi-GB weights or claim constant GPU load.'}


def evaluate_main(root, reference_root, repo):
    protocol, evaluation, source, draft, packets, oracle, hashes = base.load_inputs(reference_root, repo)
    base.old.require(base.old.file_hash(Path(base.__file__)) == REFERENCE_SCORER, 'reference_scorer_changed')
    hashes[str(Path(base.__file__).resolve())] = REFERENCE_SCORER
    previous = bound_read(reference_root / 'metrics.json', hashes, REFERENCE_METRICS)
    for name, expected in previous['input_file_sha256'].items():
        base.old.require(base.old.file_hash(name) == expected, 'reference_run_changed:' + name)
        hashes[name] = expected
    candidate_protocol = bound_read(root / 'protocol.json', hashes, CANDIDATE_PROTOCOL)
    lineage = bound_read(root / 'comparison-protocol.json', hashes, COMPARISON_PROTOCOL)
    base.old.require(candidate_protocol['model'] == lineage['model'] == MODEL
        and lineage['baseline_model'] == protocol['model']
        and lineage['baseline_protocol_sha256'] == base.SCRIPT_PROTOCOL
        and lineage['protocol_sha256'] == CANDIDATE_PROTOCOL
        and Path(lineage['baseline_root']).resolve() == reference_root.resolve(), 'candidate_protocol_identity_mismatch')
    base.old.require(base.old.digest({k: v for k, v in candidate_protocol.items() if k not in ('model', 'frozen_hashes')})
        == base.old.digest({k: v for k, v in protocol.items() if k not in ('model', 'frozen_hashes')}), 'candidate_conditions_changed')
    for name, expected in candidate_protocol['frozen_hashes'].items():
        path = root / 'frozen' / name
        base.old.require(base.old.file_hash(path) == expected, 'candidate_harness_changed:' + name)
        hashes[str(path.resolve())] = expected
    driver = root / 'frozen/run_script_review_comparison.py'
    base.old.require(base.old.file_hash(driver) == lineage['driver_sha256'], 'comparison_driver_changed')
    hashes[str(driver.resolve())] = lineage['driver_sha256']
    delta = lineage['transport_delta']
    original_path = reference_root / 'frozen/run_script_context_review.py'
    variant_path = root / 'frozen/run_script_context_review.py'
    original = original_path.read_bytes()
    base.old.require(original.count(delta['before'].encode()) == 1
        and original.replace(delta['before'].encode(), delta['after'].encode()) == variant_path.read_bytes(),
        'transport_change_exceeds_model_selection')
    # The source base is always the independently bound 9B input, never a newly
    # generated oracle, source subset or model-specific prompt configuration.
    for name, expected in lineage['copied_artifact_sha256'].items():
        base.old.require(base.old.file_hash(reference_root / name) == expected, 'reference_copy_changed:' + name)
        bound_read(root / name, hashes, expected)
    conditions = dict(protocol, model=MODEL)
    baseline, before = base.assess(base.normalized(draft), oracle, evaluation)
    repeats = []
    for repeat in range(1, protocol['repeats'] + 1):
        run_rows, decisions = [], {}
        for packet in packets:
            run, value = base.read_packet_run(root, packet, repeat, conditions, hashes)
            request = root / 'runs' / packet['packet_id'] / f'repeat-{repeat}/request.json'
            try:
                left = bound_read(reference_root / 'runs' / packet['packet_id'] / f'repeat-{repeat}/request.json', hashes)
                right = bound_read(request, hashes)
                run['same_request_except_model'] = compare_requests(left, right)
                base.old.require(run['same_request_except_model'], 'cross_model_request_mismatch')
            except (OSError, ValueError, TypeError, KeyError) as exc:
                run['valid'] = False
                run['same_request_except_model'] = False
                run['errors'].append(type(exc).__name__ + ':' + str(exc))
            run_rows.append(run)
            if run['valid']:
                decisions[packet['packet_id']] = value
        folder = root / 'final' / f'repeat-{repeat}'
        item = {'repeat': repeat, 'packet_runs': run_rows, 'valid': False, 'errors': [],
                'observed_final': (folder / 'projection.json').is_file() or (folder / 'failure.json').is_file(),
                'quality_after': None, 'comparison_to_9b': None}
        if all(r['valid'] for r in run_rows):
            try:
                projected = base.replay(draft, packets, decisions, source['items'])
                actual = bound_read(folder / 'projection.json', hashes)
                converted = bound_read(folder / 'normalized.json', hashes)
                base.old.require(base.old.digest(actual) == base.old.digest(projected)
                    and base.old.digest(converted) == base.old.digest(base.normalized(projected)), 'final_patch_replay_mismatch')
                quality, groups = base.assess(converted, oracle, evaluation)
                base.old.require(quality['structural_valid'], 'invalid_final_partition')
                reference = previous['repeats'][repeat - 1]
                base.old.require(reference['repeat'] == repeat and reference['valid'], 'invalid_reference_repeat')
                reference_projection = bound_read(reference_root / 'final' / f'repeat-{repeat}/projection.json', hashes)
                _, reference_groups = base.assess(base.normalized(reference_projection), oracle, evaluation)
                comparison = compare_ledgers(reference['ledger'], projected['ledger'])
                comparison.update(partition_match=quality['partition_sha256'] == reference['quality_after']['partition_sha256'],
                    annotations_match=base.old.partition_hash(groups, annotated=True) == base.old.partition_hash(reference_groups, annotated=True),
                    figure_companions_match=base.old.digest(projected['figures']) == base.old.digest(reference_projection['figures']))
                old_probes = {p['id']: p['passed'] for p in baseline['probes']}
                item.update(valid=True, quality_after=quality, unresolved=projected['unresolved'],
                    review_complete=not projected['unresolved'], ledger=projected['ledger'],
                    decision_counts=dict(Counter(r['decision'] for r in projected['ledger'])),
                    merged_boundary_issue_ids=[r['issue'] for r in projected['ledger'] if r['decision'] == 'merge_previous'],
                    reason_code_diagnostics=base.reason_diagnostics(packets, decisions),
                    delta_from_draft=base.compare(before, groups, oracle), comparison_to_9b=comparison,
                    newly_passed_probes=[p['id'] for p in quality['probes'] if p['passed'] and not old_probes[p['id']]],
                    newly_failed_probes=[p['id'] for p in quality['probes'] if not p['passed'] and old_probes[p['id']]])
            except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
                item['errors'].append(type(exc).__name__ + ':' + str(exc))
        else:
            item['errors'].append('invalid_or_missing_packet_results')
            if (folder / 'failure.json').is_file():
                bound_read(folder / 'failure.json', hashes)
        repeats.append(item)
    valid = [r for r in repeats if r['valid']]
    runs = [p for r in repeats for p in r['packet_runs']]
    reference_runs = [p for r in previous['repeats'] for p in r['packet_runs']]
    report = {'schema_version': 'script-review-model-comparison-v1', 'reference_model': protocol['model'], 'model': MODEL,
        'draft': baseline, 'repeats': repeats,
        'state': 'complete' if all(r['observed_final'] and all(p['result_present'] for p in r['packet_runs']) for r in repeats) else 'partial',
        'summary': {'expected_model_calls': len(packets) * protocol['repeats'],
            'observed_model_calls': sum(p['response_present'] for p in runs), 'valid_model_calls': sum(p['valid'] for p in runs),
            'valid_repeats': len(valid), 'review_complete_repeats': sum(r['review_complete'] for r in valid),
            'same_partition_as_9b_repeats': sum(r['comparison_to_9b']['partition_match'] for r in valid),
            'same_annotations_as_9b_repeats': sum(r['comparison_to_9b']['annotations_match'] for r in valid),
            'same_figure_companions_as_9b_repeats': sum(r['comparison_to_9b']['figure_companions_match'] for r in valid),
            'unique_valid_4b_partitions': len({r['quality_after']['partition_sha256'] for r in valid}),
            'all_requests_same_except_model': all(p['same_request_except_model'] for p in runs),
            'reason_code_issue_type_mismatches': sum(r['reason_code_diagnostics']['issue_type_mismatch_count'] for r in valid),
            'needs_context_without_insufficient_context': sum(r['reason_code_diagnostics']['needs_context_without_insufficient_context_count'] for r in valid),
            'insufficient_context_on_decisive_choice': sum(r['reason_code_diagnostics']['insufficient_context_on_decisive_choice_count'] for r in valid),
            'issues_compared': sum(r['comparison_to_9b']['issues'] for r in valid),
            **{key + '_count': sum(r['comparison_to_9b'][key + '_count'] for r in valid) for key in
               ('decision_match', 'evidence_set_match', 'evidence_order_match', 'reason_code_match')}},
        'usage_and_timing': {'candidate': usage_summary(runs), 'reference': usage_summary(reference_runs)},
        'runtime': runtime_metadata(root, reference_root, hashes),
        'definitions': {'request_equality': 'Exact serialized policy/source/schema/generation conditions; only model label may differ. Model weights, quantization and tokenizer differ.',
            'partition': 'Ignores group label/order; annotations additionally compare kind/figure_refs. Figure companions compare complete deterministic figure records.',
            'evidence': 'Evidence set agreement and array-order agreement are reported separately. Neither proves the evidence is substantively sufficient.',
            'scope': 'Same known Test_Paper and20 issues repeated3 times; no blind-oracle or generalization claim. Figure1 packing preference and reason-code post-hoc rubric remain as in the9B evaluation.',
            'calls': 'Formal21-call arm only; smoke and the separate control are excluded. Observed calls have response artifacts.',
            'timing': 'Sum/median of recorded packet seconds, not overall wall time; includes packet preflight. Different tokenizers make token totals measurements, not an input-equality test.',
            'performance_confounders': 'Compares4B Q4_0 with9B Q8_0, not parameter count alone. Quantization, tokenizer and GPU load can affect timing; this is not an isolated hardware benchmark.'},
        'scorer_model_calls': 0, 'scorer_database_calls': 0, 'scorer_existing_source_writes': 0}
    return report, hashes, conditions


def evaluate_control(root, reference_root, protocol, hashes):
    control = bound_read(reference_root / 'controls/protocol.json', hashes, REFERENCE_CONTROL)
    packet = bound_read(reference_root / 'controls/packet.json', hashes, control['packet_sha256'])
    expected = bound_read(reference_root / 'controls/expected.json', hashes, control['expected_sha256'])
    for name, digest in (('packet.json', control['packet_sha256']), ('expected.json', control['expected_sha256'])):
        if (root / 'controls' / name).exists():
            bound_read(root / 'controls' / name, hashes, digest)
    run, value = base.read_packet_run(root / 'controls', packet, 1, protocol, hashes)
    old_request = bound_read(reference_root / 'controls/runs/sensitivity/repeat-1/request.json', hashes)
    new_path = root / 'controls/runs/sensitivity/repeat-1/request.json'
    if new_path.is_file():
        match = compare_requests(old_request, bound_read(new_path, hashes))
        if not match:
            run['valid'] = False
            run['errors'].append('control_request_not_same_except_model')
    else:
        match = False
    old_run, old_decisions = base.read_packet_run(reference_root / 'controls', packet, 1,
        dict(protocol, model='qwen35-9b-q8'), hashes)
    base.old.require(old_run['valid'], 'reference_control_invalid')
    checks = [{'issue': issue, 'expected': choice,
        'candidate': value[issue]['decision'] if run['valid'] else None,
        'reference': old_decisions[issue]['decision'],
        'candidate_passed': bool(run['valid'] and value[issue]['decision'] == choice),
        'reference_passed': old_decisions[issue]['decision'] == choice} for issue, choice in expected.items()]
    return {'scope': control['scope'], 'expected_model_calls': 1, 'faults': 2,
        'run': run, 'reference_run': old_run, 'same_request_except_model': match, 'checks': checks,
        'candidate_passed_faults': sum(c['candidate_passed'] for c in checks),
        'reference_passed_faults': sum(c['reference_passed'] for c in checks),
        'excluded_from_main21_calls_and18_probes': True}


def markdown(report):
    summary = report['summary']
    lines = ['# 동일한 스크립트 초안: Qwen3.5 4B Q4_0와 9B Q8_0 비교', '',
        f"정식 검토 21회의 유효 결과는 {summary['valid_model_calls']}개입니다. 최종 그룹 구성이 9B와 같은 반복은 {summary['same_partition_as_9b_repeats']}/3입니다.", '',
        '| 반복 | 유효 | 그룹 수 | 9B와 같은 그룹 구성 | Metadata 오분류 ID | 미해결 | 새로 실패한 probe |',
        '|---|---|---:|---|---|---|---|']
    for row in report['repeats']:
        if row['valid']:
            lines.append(f"|{row['repeat']}|예|{row['quality_after']['groups_count']}|{row['comparison_to_9b']['partition_match']}|{row['quality_after']['quality']['metadata_false_positive_ids']}|{row['unresolved']}|{row['newly_failed_probes']}|")
        else:
            lines.append(f"|{row['repeat']}|아니오|—|—|—|—|—|")
    lines += ['', f"비교한 결정 {summary['issues_compared']}개 중 선택이 같은 것은 {summary['decision_match_count']}개, 근거 집합이 같은 것은 {summary['evidence_set_match_count']}개, 근거 순서까지 같은 것은 {summary['evidence_order_match_count']}개, reason_code가 같은 것은 {summary['reason_code_match_count']}개입니다.", '',
        'Figure 1의 실제 두 소절 유지와 참조 묶음의 차이는 허용되는 구성 차이입니다. reason_code 호환성은 9B 결과 관찰 후 추가된 별도 진단이며, 코드 불일치만으로 결정 자체가 의미적으로 틀렸다고 판정하지 않습니다.', '',
        '원문·정책·출력 스키마·생성 설정의 동일성은 모델명만 제외한 실제 요청 비교로 확인합니다. 모델·양자화·토크나이저가 달라 실제 토큰 수는 달라질 수 있습니다.', '',
        '속도는 4B Q4_0와 9B Q8_0의 관찰값입니다. 실행 전 GPU 부하도 달랐으므로 모델 크기만의 효과나 동일 부하의 하드웨어 벤치마크로 해석하지 않습니다. 실제 모델의 SHA, 읽기 전용 마운트, 서버 속성과 GPU 시작 스냅샷을 metrics.json에 결속했습니다.', '',
        f"별도 오류 주입 검사는 2건 중 4B가 {report['control']['candidate_passed_faults']}건, 9B가 {report['control']['reference_passed_faults']}건을 통과했습니다. 정식 평가 21회 및 사전 probe 18개와 합산하지 않습니다.", '',
        '이 결과는 이미 알려진 논문 1편과 동일한 이슈 20개의 반복 비교입니다. 다른 문서의 일반화 성능이나 원문 이미지의 시각 검증을 입증하지 않습니다. 상세 hash·근거 ID·선택·이유 코드·토큰 사용량·시간은 metrics.json에 보존합니다.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('output/t03-script-context-review-4b'))
    parser.add_argument('--reference-root', type=Path, default=Path('output/t03-script-context-review'))
    parser.add_argument('--repo', type=Path, default=Path('.'))
    args = parser.parse_args()
    root, reference_root, repo = (p.resolve(strict=True) for p in (args.root, args.reference_root, args.repo))
    report, hashes, protocol = evaluate_main(root, reference_root, repo)
    report['control'] = evaluate_control(root, reference_root, protocol, hashes)
    base.old.require(report['state'] == 'complete' and report['control']['run']['result_present'], 'runs_incomplete_no_metrics_written')
    targets = (root / 'metrics.json', root / 'EVALUATION.md')
    base.old.require(not any(p.exists() for p in targets), 'comparison_output_already_exists')
    report['input_file_sha256'] = hashes
    report['comparator_sha256'] = base.old.file_hash(__file__)
    base.old.require(all(base.old.file_hash(name) == digest for name, digest in hashes.items()), 'input_changed_during_comparison')
    with targets[0].open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    with targets[1].open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(markdown(report))
    print(json.dumps({'state': report['state'], **report['summary'], 'metrics_sha256': base.old.file_hash(targets[0])}))


if __name__ == '__main__':
    main()
