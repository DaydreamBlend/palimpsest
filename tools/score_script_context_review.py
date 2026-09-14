"""Offline paired evaluation of the frozen Test_Paper script/reviewer experiment.

Imports only the offline scorer, never the generation harness. Reference packing
agreement and policy-compatible subsection boundaries are reported separately.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from itertools import combinations
import json
import math
from pathlib import Path
import statistics

import score_context_grouping_experiment as old

SCRIPT_PROTOCOL = '3c73a2c05640825130a6ff5500ae7bb472d1d1c1e7ab1c0da81344e66d2922ff'
EVALUATION_PROTOCOL = '5d2485930f01dcc3adfededb13d1b89e9237474179133cb6200ab5eb4bc6a326'
REASONS = ['source_structure', 'study_overview', 'front_metadata', 'real_subsection',
           'false_boundary', 'explicit_caption', 'insufficient_context']
TYPE_REASONS = {
    'front_role': ['source_structure', 'study_overview', 'front_metadata', 'insufficient_context'],
    'boundary': ['source_structure', 'real_subsection', 'false_boundary', 'insufficient_context'],
    'caption_link': ['source_structure', 'explicit_caption', 'insufficient_context'],
}


def normalized(projection):
    return {'groups': [{key: group[key] for key in ('kind', 'items', 'figure_refs')}
                       for group in projection['groups']]}


def load_inputs(root, repo):
    hashes = {}

    def read(path, expected=None):
        actual = old.file_hash(path)
        old.require(expected is None or actual == expected, 'frozen_input_changed:' + str(path))
        hashes[str(path.resolve())] = actual
        return old.read(path)

    protocol = read(root / 'protocol.json', SCRIPT_PROTOCOL)
    evaluation = read(root / 'evaluation_protocol.json', EVALUATION_PROTOCOL)
    for name, expected in protocol['frozen_hashes'].items():
        path = root / 'frozen' / name
        old.require(old.file_hash(path) == expected, 'frozen_harness_changed:' + name)
        hashes[str(path.resolve())] = expected
    for name, expected in protocol['input_hashes'].items():
        read(repo / Path(name), expected)
    for name, expected in protocol['artifact_hashes'].items():
        read(root / name, expected)
    source, draft, packets = (read(root / name) for name in ('source.json', 'draft.json', 'packets.json'))
    stored_normalized = read(root / 'draft-normalized.json')
    old.require(old.digest(stored_normalized) == old.digest(normalized(draft)), 'draft_normalization_mismatch')
    cases, oracles, _, oracle_paths, oracle_hashes = old.load_oracles(repo / 'output/t03-context-models')
    for key, path in oracle_paths.items():
        hashes[str(path.resolve())] = oracle_hashes[key]
    old.require(old.file_hash(Path(old.__file__)) == evaluation['inputs']['scorer_sha256'], 'old_scorer_changed')
    hashes[str(Path(old.__file__).resolve())] = evaluation['inputs']['scorer_sha256']
    oracle = oracles['Test_Paper']
    analysis = read(oracle_paths['paper_oracle'], evaluation['inputs']['oracle_sha256'])
    rows = source['items']
    old.require(old.digest(rows) == old.digest([{'id': n, **row} for n, row in enumerate(analysis['information'])]),
                'source_record_or_provenance_changed')
    bundle = read(repo / 'output/t03-image-default/evidence/source_bundle.json')
    old.require(old.digest(source['pages']) == old.digest(bundle['pages']), 'source_page_provenance_changed')
    blocks = {block['block_id']: block for block in bundle['blocks']}
    old.require(len(blocks) == len(rows) == 229, 'source_coverage_changed')
    for row in rows:
        block = blocks[row['block_id']]
        old.require(row['content'] == block['text'] and row['page_number'] == block['page_index'] + 1
                    and row['source_type'] == block['type'], 'source_not_raw_parser_content')
    visual = read(repo / 'output/t03-image-default/evidence/visuals/manifest.json')
    panels = {p['panel_id']: p for p in visual['panels']}
    block_ids = {row['block_id']: row['id'] for row in rows}
    for figure, raw in zip(draft['figures'], visual['figures'], strict=True):
        expected = {block_ids[a['source_block_id']] for a in raw['caption_anchors']}
        expected.update(block_ids[panels[p]['source_block_id']] for p in raw['member_panel_ids'])
        old.require(old.digest(figure['source_figure']) == old.digest(raw)
                    and figure['items'] == sorted(expected), 'figure_evidence_not_source_bound')
    old.require([p['packet_id'] for p in packets] == protocol['packet_ids'], 'packet_inventory_changed')
    for packet in packets:
        old.require(set(packet) == {'packet_id', 'issues', 'source_ids', 'source', 'draft_groups', 'figure_evidence'},
                    'packet_fields_not_allowlisted')
        expected = [{key: rows[i][key] for key in ('id', 'page_number', 'source_type', 'content')}
                    for i in packet['source_ids']]
        old.require(old.digest(packet['source']) == old.digest(expected), 'packet_source_not_exact_allowlist')
        for issue in packet['issues'].values():
            old.require(set(issue['source_ids']) <= set(packet['source_ids']), 'issue_source_outside_packet')
    return protocol, evaluation, source, draft, packets, oracle, hashes


def schema(packet):
    properties = {}
    for key, issue in packet['issues'].items():
        properties[key] = {'type': 'object', 'properties': {
            'decision': {'type': 'string', 'enum': issue['options']},
            'evidence_ids': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'uniqueItems': True,
                             'items': {'type': 'integer', 'enum': issue['source_ids']}},
            'reason_code': {'type': 'string', 'enum': REASONS}},
            'required': ['decision', 'evidence_ids', 'reason_code'], 'additionalProperties': False}
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def validate_decisions(value, packet):
    old.require(isinstance(value, dict) and set(value) == set(packet['issues']), 'issue_key_coverage')
    for key, issue in packet['issues'].items():
        row = value[key]
        old.require(isinstance(row, dict) and set(row) == {'decision', 'evidence_ids', 'reason_code'}, 'decision_fields')
        old.require(row['decision'] in issue['options'] and row['reason_code'] in REASONS, 'decision_enum')
        ids = row['evidence_ids']
        old.require(isinstance(ids, list) and 1 <= len(ids) <= 4
                    and all(type(i) is int and i in issue['source_ids'] for i in ids)
                    and len(ids) == len(set(ids)), 'invalid_decision_evidence')
        old.require(set(ids) & set(issue['target_ids']), 'target_evidence_required')
    return value


def reason_diagnostics(packets, decisions):
    """Post-hoc code compatibility only; does not change decision validity."""
    rows = []
    for packet in packets:
        for key, issue in packet['issues'].items():
            value = decisions[packet['packet_id']][key]
            code, choice = value['reason_code'], value['decision']
            rows.append({'packet_id': packet['packet_id'], 'issue': key, 'issue_type': issue['type'],
                'decision': choice, 'reason_code': code,
                'issue_type_mismatch': code not in TYPE_REASONS[issue['type']],
                'needs_context_without_insufficient_context': choice == 'needs_context' and code != 'insufficient_context',
                'insufficient_context_on_decisive_choice': choice != 'needs_context' and code == 'insufficient_context'})
    return {'issues_count': len(rows),
        **{key + '_count': sum(row[key] for row in rows) for key in
           ('issue_type_mismatch', 'needs_context_without_insufficient_context', 'insufficient_context_on_decisive_choice')},
        'rows': rows}


def read_packet_run(root, packet, repeat, protocol, hashes):
    folder = root / 'runs' / packet['packet_id'] / f'repeat-{repeat}'
    values, errors, request_bound = {}, [], False
    for name in ('request', 'response', 'decisions', 'result'):
        path = folder / (name + '.json')
        try:
            hashes[str(path.resolve())] = old.file_hash(path)
            values[name] = old.read(path)
        except (OSError, ValueError) as exc:
            errors.append(name + ':' + type(exc).__name__)
    result = values.get('result')
    if not isinstance(result, dict):
        result = {}
    try:
        prompt = protocol['policy'] + '\nSOURCE_JSON:\n' + json.dumps(packet, ensure_ascii=False, separators=(',', ':'))
        expected = {key: protocol[key] for key in ('model', 'temperature', 'seed', 'max_tokens', 'reasoning_budget_tokens')}
        expected.update(messages=[{'role': 'user', 'content': prompt}], stream=False, cache_prompt=False,
            chat_template_kwargs={'enable_thinking': True}, response_format={'type': 'json_object', 'schema': schema(packet)})
        old.require(old.digest(values['request']) == old.digest(expected), 'request_not_frozen_packet_and_config')
        request_bound = True
        old.require(result.get('valid') is True and result.get('errors') == [], 'runner_invalid')
        old.require(result['packet_id'] == packet['packet_id'] and type(result['repeat']) is int
                    and result['repeat'] == repeat, 'result_identity_mismatch')
        old.require(result['request_sha256'] == hashes[str((folder / 'request.json').resolve())], 'request_receipt_mismatch')
        tokens = result['templated_prompt_tokens']
        old.require(type(tokens) is int and tokens > 0 and tokens + 1 + protocol['max_tokens'] <= protocol['context_size'],
                    'prompt_context_receipt_invalid')
        choice = values['response']['choices'][0]
        old.require(choice['finish_reason'] == 'stop', 'finish_reason_not_stop')
        # Only content is used; hidden reasoning is never inspected or scored.
        parsed = validate_decisions(old.parse_json(choice['message']['content']), packet)
        old.require(old.digest(parsed) == old.digest(values['decisions']), 'decisions_not_raw_response')
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        errors.append(type(exc).__name__ + ':' + str(exc))
    seconds = result.get('seconds')
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        seconds = None
    row = {'packet_id': packet['packet_id'], 'repeat': repeat, 'valid': not errors, 'errors': errors,
           'request_bound_to_frozen_packet': request_bound,
           'response_present': str((folder / 'response.json').resolve()) in hashes,
           'result_present': 'result' in values, 'seconds': seconds,
           'templated_prompt_tokens': result.get('templated_prompt_tokens'), 'usage': result.get('usage')}
    return row, values.get('decisions') if not errors else None


def replay(draft, packets, decisions, rows):
    """Independent replay of the three allowed operations; no model or oracle."""
    groups = {g['group_id']: deepcopy(g) for g in draft['groups']}
    parent = {i: i for i in groups}

    def owner(i):
        while parent[i] != i:
            i = parent[i]
        return i

    abstract, ledger = [], []
    for packet in packets:
        value = validate_decisions(decisions[packet['packet_id']], packet)
        for key, issue in packet['issues'].items():
            row, status = value[key], 'unchanged'
            if row['decision'] == 'abstract':
                old.require(issue['type'] == 'front_role', 'abstract_outside_front_role')
                abstract.extend(issue['target_ids'])
                status = 'applied'
            elif row['decision'] == 'merge_previous':
                old.require(issue['type'] == 'boundary', 'merge_outside_boundary')
                left, right = owner(issue['left_group']), owner(issue['right_group'])
                old.require(groups[left]['kind'] == groups[right]['kind'], 'cross_kind_merge')
                if left != right:
                    groups[left]['items'].extend(groups[right]['items'])
                    groups[right]['items'] = []
                    parent[right] = left
                status = 'applied'
            elif row['decision'] == 'needs_context':
                status = 'unresolved'
            ledger.append({'issue': key, 'status': status, **row})
    if abstract:
        old.require(set(abstract) <= set(groups[0]['items']), 'abstract_not_in_metadata')
        groups[0]['items'] = sorted(set(groups[0]['items']) - set(abstract))
        label = len(groups)
        groups[label] = {'group_id': label, 'kind': 'abstract', 'title': 'Unlabeled abstract (model proposal)', 'items': sorted(abstract)}
    for group in groups.values():
        group['items'] = sorted(group['items'])
        refs = set().union(*(old.references(rows[i]['content']) for i in group['items']))
        group['figure_refs'] = [{'scope': scope, 'number': number} for scope, number in sorted(refs)]
    ordered = sorted((g for g in groups.values() if g['items']), key=lambda g: min(g['items']))
    figures = deepcopy(draft['figures'])
    asset_ids = {i for f in figures for i in f['items']}
    for figure in figures:
        figure['owner_group'] = owner(figure['owner_group'])
        figure['context_groups'] = [g['group_id'] for g in ordered if any(
            ('main', figure['number']) in old.references(rows[i]['content']) for i in g['items'] if i not in asset_ids)]
    return {'groups': ordered, 'figures': figures, 'ledger': ledger,
            'unresolved': [r['issue'] for r in ledger if r['status'] == 'unresolved'], 'canonical_writes': 0}


def probe_results(groups, evaluation):
    owned = {i: g for g in groups for i in g['items']}
    rows = []
    for probe in evaluation['probes']:
        kind, status = probe['kind'], False
        ids = set(probe.get('items', probe.get('expected_items', [])))
        if kind in ('same_group', 'exact_group', 'best_overlap_and_exact_group'):
            same = ids <= owned.keys() and len({owned[i]['index'] for i in ids}) == 1
            status = same and (kind == 'same_group' or owned[min(ids)]['items'] == ids)
            status = status and all(i not in owned or owned[i]['index'] != owned[min(ids)]['index']
                                    for i in probe.get('must_not_share_with', []))
        elif kind == 'exact_partition_on_subset':
            expected = {frozenset(group) for group in probe['expected_groups']}
            universe = set().union(*expected)
            actual = {frozenset(g['items']) for g in groups if g['items'] & universe}
            status = actual == expected
        elif kind in ('metadata_positive', 'metadata_negative'):
            status = ids <= owned.keys() and all((owned[i]['kind'] == 'metadata') == (kind == 'metadata_positive') for i in ids)
        elif kind == 'group_explicit_reference_union':
            status = True
            for i in probe['source_items']:
                expected = {(r['scope'], r['number']) for r in probe['expected_source_references'][str(i)]}
                status = status and i in owned and expected <= owned[i]['refs']
        rows.append({'id': probe['id'], 'passed': status,
                     'interpretation': 'packing_preference_not_semantic_failure' if probe['id'] in
                     ('figure1_two_related_subsections', 'figure1_full_membership') else 'targeted_reference_probe'})
    return rows


def assess(value, oracle, evaluation):
    errors, groups, coverage = old.validate(value, oracle['ids'])
    quality = old.score_groups(groups, oracle)
    metadata = {i for g in groups if g['kind'] == 'metadata' for i in g['items']}
    quality['metadata_false_positive_ids'] = sorted(metadata - oracle['metadata'])
    quality['metadata_false_negative_ids'] = sorted(oracle['metadata'] - metadata)
    return {'structural_valid': not errors, 'errors': errors, 'coverage': coverage,
            'quality': quality if not errors else None, 'partial_diagnostic': quality if errors else None,
            'probes': probe_results(groups, evaluation), 'groups_count': len(groups),
            'partition_sha256': old.partition_hash(groups) if not errors else None}, groups


def same_pairs(groups, universe):
    return {pair for g in groups for pair in combinations(sorted(g['items'] & universe), 2)}


def compare(before, after, oracle):
    universe = oracle['primary']
    all_pairs = set(combinations(sorted(universe), 2))
    gold = {pair for group in oracle['groups'] for pair in combinations(sorted(group & universe), 2)}
    draft, final = same_pairs(before, universe), same_pairs(after, universe)
    corrected_splits, corrected_merges = gold & (final - draft), (draft - final) - gold
    introduced_splits, introduced_merges = gold & (draft - final), (final - draft) - gold
    changed = draft ^ final
    before_wrong, after_wrong = draft ^ gold, final ^ gold
    return {'primary_pair_universe': len(all_pairs), 'corrected_false_splits': len(corrected_splits),
        'corrected_false_merges': len(corrected_merges), 'introduced_false_splits': len(introduced_splits),
        'introduced_false_merges': len(introduced_merges), 'unchanged_correct': len(all_pairs - before_wrong - after_wrong),
        'unchanged_incorrect': len(before_wrong & after_wrong),
        'primary_changed_pair_ids': [list(pair) for pair in sorted(changed)],
        'primary_changed_information_ids': sorted({i for pair in changed for i in pair}),
        'all_changed_information_ids': sorted({i for pair in same_pairs(before, oracle['ids']) ^ same_pairs(after, oracle['ids']) for i in pair})}


def evaluate(root, repo, *, draft_only=False):
    protocol, evaluation, source, draft, packets, oracle, hashes = load_inputs(root, repo)
    baseline, before = assess(normalized(draft), oracle, evaluation)
    old.require(baseline['structural_valid'], 'invalid_frozen_draft')
    report = {'schema_version': 'script-context-review-metrics-v1', 'draft': baseline, 'repeats': [],
        'scope': evaluation['scope'], 'model': protocol['model'], 'expected_repeats': protocol['repeats'],
        'source_information_count': 229, 'source_provenance_bound': True,
        'leakage_audit': {'builder_code_review': 'No semantic oracle groups or evaluator input are read by the frozen builder. source-map.items is rebound to parser block text/type/page; imported modules only provide I/O, schema validation and transport functions.',
                         'packet_source_allowlist_checked': True, 'serialized_requests_all_bound': None,
                         'model_input_modalities': 'text only; original page pixels are not supplied to this reviewer.'},
        'interpretation': ['Figure1 retains two real Results subsections under the new policy. The reviewed packing merges them; its28 differing pairs are a packing preference, not28 semantic errors.',
            'Abstract I57 is a singleton in the fixed primary universe. Correcting its metadata role does not change primary pairF1; report its exact-group probe and metadata false positives.',
            'Caption links and figure_refs are source-derived script outputs. Their preservation is not evidence of new model extraction or visual validation.',
            'needs_context remains unresolved even when the resulting partition passes structural validation.'],
        'preflight_updates': 'Before inference, implementation checks added source-block uniqueness, exclusive writes, source-order final groups, Figure context rebasing, unique evidence IDs and target-evidence validation. Frozen source/draft did not change; this was not model-output tuning.',
        'posthoc_reason_code_rubric': {'timing': 'Added after a qualitative reviewer observed a boundary decision labeled explicit_caption; not one of the preplanned18 probes.',
            'allowed_by_issue_type': TYPE_REASONS,
            'uncertainty_code': 'Report needs_context without insufficient_context, and insufficient_context with a decisive choice, separately.',
            'interpretation': 'Reason-code compatibility is a reporting diagnostic, not a semantic decision failure or an additional structural validation gate. Raw decisions are unchanged.'},
        'scorer_model_calls': 0, 'scorer_database_calls': 0, 'scorer_existing_source_writes': 0}
    if draft_only:
        return report, hashes
    for repeat in range(1, protocol['repeats'] + 1):
        run_rows, decisions = [], {}
        for packet in packets:
            row, decision = read_packet_run(root, packet, repeat, protocol, hashes)
            run_rows.append(row)
            if decision is not None:
                decisions[packet['packet_id']] = decision
        folder = root / 'final' / f'repeat-{repeat}'
        final, errors = None, []
        observed_final = any((folder / name).is_file() for name in ('projection.json', 'failure.json'))
        if all(r['valid'] for r in run_rows):
            try:
                final = replay(draft, packets, decisions, source['items'])
                for name, expected in (('projection.json', final), ('normalized.json', normalized(final))):
                    path = folder / name
                    hashes[str(path.resolve())] = old.file_hash(path)
                    old.require(old.digest(old.read(path)) == old.digest(expected), 'final_not_exact_patch_replay:' + name)
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append(type(exc).__name__ + ':' + str(exc))
        else:
            errors.append('invalid_or_missing_packet_results')
            if (folder / 'failure.json').is_file():
                path = folder / 'failure.json'
                hashes[str(path.resolve())] = old.file_hash(path)
        item = {'repeat': repeat, 'packet_runs': run_rows, 'observed_final': observed_final,
                'valid': not errors, 'errors': errors, 'quality_after': None}
        if not errors:
            after_score, after = assess(normalized(final), oracle, evaluation)
            item.update(valid=after_score['structural_valid'], quality_after=after_score,
                unresolved=final['unresolved'], review_complete=not final['unresolved'],
                decision_counts=dict(Counter(r['decision'] for r in final['ledger'])),
                merged_boundary_issue_ids=[r['issue'] for r in final['ledger'] if r['decision'] == 'merge_previous'],
                reason_code_diagnostics=reason_diagnostics(packets, decisions),
                ledger=final['ledger'], delta=compare(before, after, oracle))
            item['delta']['primary_pairwise_f1'] = after_score['quality']['primary_pairwise']['f1'] - baseline['quality']['primary_pairwise']['f1']
            item['delta']['metadata_fp_count'] = len(after_score['quality']['metadata_false_positive_ids']) - len(baseline['quality']['metadata_false_positive_ids'])
            previous = {p['id']: p['passed'] for p in baseline['probes']}
            item['delta']['newly_passed_probes'] = [p['id'] for p in after_score['probes'] if p['passed'] and not previous[p['id']]]
            item['delta']['newly_failed_probes'] = [p['id'] for p in after_score['probes'] if not p['passed'] and previous[p['id']]]
        report['repeats'].append(item)
    report['state'] = 'complete' if all(r['observed_final'] and all(p['result_present'] for p in r['packet_runs'])
                                      for r in report['repeats']) else 'partial'
    report['leakage_audit']['serialized_requests_all_bound'] = all(
        p['request_bound_to_frozen_packet'] for r in report['repeats'] for p in r['packet_runs'])
    valid = [r for r in report['repeats'] if r['valid']]
    times = [p['seconds'] for r in report['repeats'] for p in r['packet_runs'] if p['seconds'] is not None]
    report['summary'] = {'valid_repeats': len(valid), 'review_complete_repeats': sum(r['review_complete'] for r in valid),
        'expected_model_calls': len(packets) * protocol['repeats'],
        'observed_model_calls': sum(p['response_present'] for r in report['repeats'] for p in r['packet_runs']),
        'valid_model_calls': sum(p['valid'] for r in report['repeats'] for p in r['packet_runs']),
        'model_call_scope': 'Formal packet runs only, excluding smoke. Observed calls have response.json; transport attempts without responses cannot be inferred.',
        'reason_code_issues_scored': sum(r['reason_code_diagnostics']['issues_count'] for r in valid),
        'reason_code_issue_type_mismatches': sum(r['reason_code_diagnostics']['issue_type_mismatch_count'] for r in valid),
        'needs_context_without_insufficient_context': sum(r['reason_code_diagnostics']['needs_context_without_insufficient_context_count'] for r in valid),
        'insufficient_context_on_decisive_choice': sum(r['reason_code_diagnostics']['insufficient_context_on_decisive_choice_count'] for r in valid),
        'unique_valid_partitions': len({r['quality_after']['partition_sha256'] for r in valid}),
        'packet_seconds_median_observed': statistics.median(times) if times else None,
        'packet_seconds_total_observed': sum(times), 'timing_scope': 'Observed packet calls, including invalid ones; not total wall time.'}
    return report, hashes


def markdown(report):
    d = report['draft']['quality']
    lines = ['# Script draft + bounded 9B review evaluation', '',
        '원문229개 I를 기준으로 스크립트 초안과 적용된 검토 결과를 비교했습니다. 구조적 유효성은 의미적 정확성의 증명이 아닙니다.', '',
        f"초안 primary pairF1={d['primary_pairwise']['f1']:.6f}; metadata 오분류 IDs={d['metadata_false_positive_ids']}.", '',
        '| 결과 | 유효성 | primary F1 | metadata FP IDs | 미해결 | 새 회귀 probe | reason code 유형 불일치 |',
        '|---|---|---:|---|---|---|---:|']
    for row in report['repeats']:
        if row['valid']:
            q = row['quality_after']['quality']
            lines.append(f"| repeat-{row['repeat']} | valid | {q['primary_pairwise']['f1']:.6f} | {q['metadata_false_positive_ids']} | {row['unresolved']} | {row['delta']['newly_failed_probes']} | {row['reason_code_diagnostics']['issue_type_mismatch_count']} |")
        else:
            lines.append(f"| repeat-{row['repeat']} | invalid | — | — | — | — | — |")
    lines += ['', 'Figure1의 실제 소절2개를 분리한28쌍의 차이는 허용되는 구성 차이로 기록합니다. 이를 합쳐 점수가 높아져도 현재 소절 보존 정책에 대한 의미적 개선이라고 주장하지 않습니다.', '',
        'Abstract I57의 metadata 오분류를 수정해도 primary pairF1은 변하지 않습니다. metadata FP와 Abstract exact-group probe를 함께 확인해야 합니다.', '',
        'Figure5·6의 캡션 연속성과 원격 본문 연결은 초안부터 보존됩니다. 검토기는 텍스트만 받으므로 시각 검증을 수행한 것으로 해석하지 않습니다.', '',
        'reason_code 호환성은 첫 응답의 boundary에 explicit_caption이 사용된 관찰 후 추가한 사후 진단입니다. 사전18개 probe와 구분하며, 코드 불일치만으로 결정 자체가 의미적으로 틀렸다고 판정하거나 구조적 유효성을 바꾸지 않습니다.', '',
        '초안 및 모든 적용 결과의 원문·페이지·Figure 근거는 hash로 결속했습니다. 입력에 semantic oracle groups가 포함되지 않은 경로를 코드와 직렬화된 요청으로 확인합니다. 상세 coverage,18개 probe,개선·회귀 pair와 실행 근거 hash는 metrics.json에 있습니다.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('output/t03-script-context-review'))
    parser.add_argument('--repo', type=Path, default=Path('.'))
    parser.add_argument('--draft-only', action='store_true', help='Read-only draft evaluation; no final files written.')
    args = parser.parse_args()
    root, repo = args.root.resolve(strict=True), args.repo.resolve(strict=True)
    report, hashes = evaluate(root, repo, draft_only=args.draft_only)
    if args.draft_only:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    old.require(report['state'] == 'complete', 'final_runs_incomplete_no_metrics_written')
    targets = (root / 'metrics.json', root / 'EVALUATION.md')
    old.require(not any(p.exists() for p in targets), 'evaluation_output_already_exists')
    report['input_file_sha256'] = hashes
    report['scorer_sha256'] = old.file_hash(__file__)
    old.require(all(old.file_hash(path) == digest for path, digest in hashes.items()), 'input_changed_during_evaluation')
    with targets[0].open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    with targets[1].open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(markdown(report))
    print(json.dumps({'state': report['state'], **report['summary'], 'metrics_sha256': old.file_hash(targets[0])}))


if __name__ == '__main__':
    main()
