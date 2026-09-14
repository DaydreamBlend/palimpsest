"""Offline scoring of frozen context groups; never imports a model client.

The PDF oracle is one reviewed packing, not semantic truth. Markdown uses the
authored line-boundary oracle. All source files are read-only; metrics.json is
created exclusively and cannot overwrite an earlier evaluation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
import json
import math
from pathlib import Path
import re
import statistics

KINDS = ('metadata', 'abstract', 'introduction', 'results', 'discussion',
         'methods', 'back_matter', 'references', 'section')
FIGURE = re.compile(r'\b(?:(Supplementary)\s+)?Figures?\s+([1-9][0-9]*)', re.I)


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def parse_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate_json_key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def read(path):
    return parse_json(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def references(text):
    """Frozen explicit Figure-number mentions, not inferred links or assets."""
    return {('supplementary' if match[1] else 'main', int(match[2]))
            for match in FIGURE.finditer(text)}


def kind_for(key):
    if key.startswith('result-'):
        return 'results'
    if key.startswith('methods-'):
        return 'methods'
    return {'source-metadata': 'metadata', 'back-matter': 'back_matter'}.get(key, key)


def expected_schema(count):
    ref = {'type': 'object', 'properties': {
        'scope': {'type': 'string', 'enum': ['main', 'supplementary']},
        'number': {'type': 'integer', 'minimum': 1}},
        'required': ['scope', 'number'], 'additionalProperties': False}
    group = {'type': 'object', 'properties': {
        'kind': {'type': 'string', 'enum': list(KINDS)},
        'items': {'type': 'array', 'minItems': 1, 'items': {
            'type': 'integer', 'minimum': 0, 'maximum': count - 1}},
        'figure_refs': {'type': 'array', 'items': ref}},
        'required': ['kind', 'items', 'figure_refs'], 'additionalProperties': False}
    return {'type': 'object', 'properties': {
        'groups': {'type': 'array', 'minItems': 1, 'items': group}},
        'required': ['groups'], 'additionalProperties': False}


def assignment_schema(count):
    label = {'type': 'integer', 'minimum': 0, 'maximum': count - 1}
    group = expected_schema(count)['properties']['groups']['items']
    group['properties'] = {'group_id': label, 'kind': group['properties']['kind'],
                           'figure_refs': group['properties']['figure_refs']}
    group['required'] = ['group_id', 'kind', 'figure_refs']
    return {'type': 'object', 'properties': {
        'assignments': {'type': 'object', 'properties': {str(i): label for i in range(count)},
                        'required': [str(i) for i in range(count)], 'additionalProperties': False},
        'groups': {'type': 'array', 'minItems': 1, 'items': group}},
        'required': ['assignments', 'groups'], 'additionalProperties': False}


def normalize_assignments(value, count):
    """Independently bind source keys to groups; malformed data stays diagnostic."""
    errors, groups = [], []
    if not isinstance(value, dict):
        return ['invalid_assignment_root'], {'groups': []}
    if set(value) != {'assignments', 'groups'}:
        errors.append('invalid_assignment_root')
    assignments, definitions = value.get('assignments'), value.get('groups')
    expected_keys = {str(i) for i in range(count)}
    if not isinstance(assignments, dict):
        assignments = {}
    if set(assignments) != expected_keys:
        errors.append('assignment_key_coverage')
    usable = {}
    for key, label in assignments.items():
        if type(label) is not int or not 0 <= label < count:
            errors.append('invalid_assignment_value')
        elif key in expected_keys:
            usable[int(key)] = label
    if not isinstance(definitions, list) or not definitions:
        errors.append('invalid_group_definitions')
        definitions = []
    labels = []
    for definition in definitions:
        if not isinstance(definition, dict):
            errors.append('invalid_group_definition')
            continue
        if set(definition) != {'group_id', 'kind', 'figure_refs'}:
            errors.append('invalid_group_definition_fields')
        label = definition.get('group_id')
        if type(label) is not int or not 0 <= label < count:
            errors.append('invalid_group_label')
            continue
        labels.append(label)
        groups.append({'kind': definition.get('kind'), 'figure_refs': definition.get('figure_refs'),
                       'items': sorted(i for i, target in usable.items() if target == label)})
    if len(set(labels)) != len(labels):
        errors.append('duplicate_group_label')
    if set(labels) != set(usable.values()):
        errors.append('unused_or_undefined_group_label')
    return errors, {'groups': groups}


def load_oracles(root):
    paths = {'cases': root / 'cases.json', 'protocol': root / 'protocol.json',
             'source_map': root / 'source-map.json',
             'paper_oracle': root.parent / 't03-information-context/analysis.json',
             'markdown_oracle': root / 'markdown_cases.json'}
    hashes = {key: file_hash(path) for key, path in paths.items()}
    data = {key: read(path) for key, path in paths.items()}
    protocol, mapping, paper = data['protocol'], data['source_map'], data['paper_oracle']
    require(hashes['cases'] == protocol['cases_sha256'], 'frozen_cases_changed')
    require(hashes['paper_oracle'] == mapping['analysis_sha256'], 'paper_oracle_changed')
    require(hashes['markdown_oracle'] == mapping['fixture_sha256'], 'markdown_oracle_changed')
    require(sha256(protocol['policy'].encode()).hexdigest() == protocol['policy_sha256'], 'policy_changed')
    require(type(protocol['repeats']) is int and protocol['repeats'] > 0, 'invalid_repeat_count')
    md = {case['case_id']: case for case in data['markdown_oracle']['cases']}
    oracles, cases = {}, {}
    for case in data['cases']['cases']:
        key, source = case['case_id'], case['input']
        require(key not in cases and set(source) == {'format', 'items'}, 'invalid_case')
        items = source['items']
        require([row['id'] for row in items] == list(range(len(items))), 'invalid_case_ids')
        require(all(set(row) == {'id', 'page', 'source_type', 'content'} for row in items), 'input_not_allowlisted')
        oracle = {'format': source['format'], 'ids': set(range(len(items))), 'groups': [],
                  'metadata': set(), 'item_refs': {}, 'figure_groups': {}, 'major_starts': {}}
        if source['format'] == 'paper':
            expected = [{'id': n, 'page': row['page_number'], 'source_type': row['source_type'],
                         'content': row['content']} for n, row in enumerate(paper['information'])]
            require(items == expected and len(items) == 229, 'paper_input_not_exact')
            require(mapping['items'] == [{'id': n, **row} for n, row in enumerate(paper['information'])],
                    'source_id_map_changed')
            ids = {row['information_id']: n for n, row in enumerate(paper['information'])}
            for group in paper['groups']:
                members = {ids[i] for i in group['information_ids']}
                oracle['groups'].append(members)
                if group['group_key'] == 'source-metadata':
                    oracle['metadata'] = members
                if group['figure_numbers']:
                    require(len(group['figure_numbers']) == 1, 'reviewed_figure_group_changed')
                    oracle['figure_groups'][group['figure_numbers'][0]] = members
                kind = kind_for(group['group_key'])
                if kind != 'metadata' and kind not in oracle['major_starts']:
                    oracle['major_starts'][kind] = min(members)
            oracle['item_refs'] = {row['id']: references(row['content']) for row in items}
            oracle['primary'] = oracle['ids'] - oracle['metadata']
            require(len(oracle['primary']) == 103 and len(oracle['metadata']) == 126,
                    'reviewed_primary_universe_changed')
        elif source['format'] == 'markdown':
            fixture = md[key]
            lines = fixture['input']['source_markdown'].splitlines()
            require(items == [{'id': n, 'page': None, 'source_type': 'line', 'content': line}
                              for n, line in enumerate(lines)], 'markdown_input_not_exact')
            expected = fixture['expected']
            require(len(lines) == expected['physical_line_count'], 'markdown_line_count_changed')
            oracle['groups'] = [set(range(start - 1, end - 1))
                                for start, end in (section['line_range'] for section in expected['sections'])]
            oracle['primary'] = oracle['ids']
            oracle['boundaries'] = {h['line'] - 1 for h in expected['headings']}
            oracle['forbidden_boundaries'] = {line - 1 for line in expected['forbidden_heading_lines']}
            oracle['item_refs'] = {i: set() for i in oracle['ids']}
            for ref in expected['figure_links']:
                value = (ref['scope'], ref['number'])
                # The frozen prompt asks for explicit references AND definitions.
                for field in ('source_line', 'target_heading_line', 'caption_line'):
                    oracle['item_refs'][ref[field] - 1].add(value)
                start, end = ref['source_character_range']
                require(references(lines[ref['source_line'] - 1][start:end]) == {value},
                        'markdown_reference_range_changed')
        else:
            raise ValueError('unknown_case_format')
        require(Counter(i for group in oracle['groups'] for i in group) == Counter(oracle['ids']),
                'oracle_not_a_partition')
        cases[key], oracles[key] = case, oracle
    return cases, oracles, protocol, paths, hashes


def validate(value, universe):
    """Independent closed-schema and coverage validation; preserve partial diagnostics."""
    errors, groups, supplied = [], [], []
    if not isinstance(value, dict) or set(value) != {'groups'} or not isinstance(value.get('groups'), list):
        errors.append('invalid_root')
        raw_groups = []
    else:
        raw_groups = value['groups']
        if not raw_groups:
            errors.append('empty_groups')
    invalid_types = 0
    for number, raw in enumerate(raw_groups):
        if not isinstance(raw, dict):
            errors.append(f'invalid_group:{number}')
            continue
        if set(raw) != {'kind', 'items', 'figure_refs'}:
            errors.append(f'invalid_group_fields:{number}')
        kind = raw.get('kind')
        if not isinstance(kind, str) or kind not in KINDS:
            errors.append(f'invalid_kind:{number}')
            kind = None
        items = raw.get('items')
        if not isinstance(items, list) or not items:
            errors.append(f'invalid_items:{number}')
            items = []
        invalid_types += sum(type(i) is not int for i in items)
        integers = [i for i in items if type(i) is int]
        if len(integers) != len(items) or any(i not in universe for i in integers):
            errors.append(f'invalid_id:{number}')
        if integers != sorted(integers):
            errors.append(f'unsorted_items:{number}')
        supplied.extend(integers)
        refs, ref_list = set(), raw.get('figure_refs')
        if not isinstance(ref_list, list):
            errors.append(f'invalid_refs:{number}')
            ref_list = []
        for ref in ref_list:
            if (not isinstance(ref, dict) or set(ref) != {'scope', 'number'}
                    or ref.get('scope') not in ('main', 'supplementary')
                    or type(ref.get('number')) is not int or ref['number'] < 1):
                errors.append(f'invalid_ref:{number}')
                continue
            key = (ref['scope'], ref['number'])
            if key in refs:
                errors.append(f'duplicate_ref:{number}')
            refs.add(key)
        groups.append({'index': number, 'kind': kind, 'items': set(integers) & universe, 'refs': refs})
    counts = Counter(supplied)
    missing = sorted(universe - counts.keys())
    duplicates = {str(i): n for i, n in sorted(counts.items()) if n > 1}
    unknown = sorted(counts.keys() - universe)
    if missing:
        errors.append('missing_ids')
    if duplicates:
        errors.append('duplicate_ids')
    unique = {i for i in universe if counts[i] == 1}
    for group in groups:
        group['items'] &= unique
    coverage = {'expected': len(universe), 'known_present': len(universe & counts.keys()),
                'exactly_once': len(unique), 'fraction_exactly_once': len(unique) / len(universe),
                'missing_ids': missing, 'duplicate_id_counts': duplicates,
                'unknown_ids': unknown, 'noninteger_id_count': invalid_types}
    return errors, groups, coverage


def prf(tp, fp, fn):
    return {'tp': tp, 'fp': fp, 'fn': fn, 'gold_support': tp + fn, 'predicted_support': tp + fp,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1.0}


def set_score(predicted, expected):
    return prf(len(predicted & expected), len(predicted - expected), len(expected - predicted))


def pair_score(groups, gold, universe):
    def pairs(partition):
        return {pair for members in partition for pair in combinations(sorted(members & universe), 2)}
    return set_score(pairs([g['items'] for g in groups]), pairs(gold))


def boundary_ids(groups):
    owner = {i: g['index'] for g in groups for i in g['items']}
    return {i for i in owner if i == 0 or owner.get(i - 1) != owner[i]}


def score_groups(groups, oracle):
    predicted = {frozenset(g['items']) for g in groups if g['items']}
    gold = {frozenset(members) for members in oracle['groups']}
    score = {'all_pairwise': pair_score(groups, oracle['groups'], oracle['ids']),
             'primary_pairwise': pair_score(groups, oracle['groups'], oracle['primary']),
             'gold_exact_groups': set_score(predicted, gold)}
    if oracle['format'] == 'paper':
        metadata = {i for g in groups if g['kind'] == 'metadata' for i in g['items']}
        score['metadata_classification'] = set_score(metadata, oracle['metadata'])
        score['per_figure_membership'] = []
        for number, members in sorted(oracle['figure_groups'].items()):
            best = max(groups, key=lambda g: (set_score(g['items'], members)['f1'],
                                             len(g['items'] & members), -g['index']), default=None)
            score['per_figure_membership'].append({'number': number,
                'best_predicted_group_index': best['index'] if best else None,
                **set_score(best['items'] if best else set(), members)})
        expected = set(oracle['major_starts'].items())
        predicted_starts = {}
        for group in groups:
            if group['items'] and group['kind'] in oracle['major_starts']:
                kind, first = group['kind'], min(group['items'])
                predicted_starts[kind] = min(first, predicted_starts.get(kind, first))
        score['major_section_starts'] = {**set_score(set(predicted_starts.items()), expected),
            'expected': oracle['major_starts'], 'predicted': predicted_starts,
            'scope': 'First owned source ID of each major role; not every printed Results subsection.'}
    else:
        predicted_boundaries = boundary_ids(groups)
        score['markdown_boundaries'] = {**set_score(predicted_boundaries, oracle['boundaries']),
            'expected_item_ids': sorted(oracle['boundaries']), 'predicted_item_ids': sorted(predicted_boundaries),
            'forbidden_boundary_ids_detected': sorted(predicted_boundaries & oracle['forbidden_boundaries']),
            'hierarchy_evaluated': False}
        score['markdown_partition_exact'] = predicted == gold
        score['markdown_noncontiguous_group_indices'] = [g['index'] for g in groups
            if g['items'] and max(g['items']) - min(g['items']) + 1 != len(g['items'])]
        score['markdown_nonsection_kind_count'] = sum(g['kind'] != 'section' for g in groups)
    links = {scope: [0, 0, 0] for scope in ('main', 'supplementary')}
    present = set()
    for group in groups:
        present.update(group['items'])
        expected = set().union(*(oracle['item_refs'][i] for i in group['items']))
        for scope in links:
            pred = {ref for ref in group['refs'] if ref[0] == scope}
            gold_refs = {ref for ref in expected if ref[0] == scope}
            for n, value in enumerate((len(pred & gold_refs), len(pred - gold_refs), len(gold_refs - pred))):
                links[scope][n] += value
    # Missing source references remain diagnostic FNs; they are never dropped
    # from the oracle. Such runs cannot enter valid-only quality aggregates.
    for i in oracle['ids'] - present:
        for scope, _ in oracle['item_refs'][i]:
            links[scope][2] += 1
    score['figure_links'] = {scope: prf(*values) for scope, values in links.items()}
    score['figure_links']['micro'] = prf(*(sum(values[n] for values in links.values()) for n in range(3)))
    supported = [result['f1'] for scope, result in score['figure_links'].items()
                 if scope != 'micro' and result['gold_support'] > 0]
    score['figure_links']['macro_f1_gold_supported_scopes'] = statistics.mean(supported) if supported else None
    return score


def partition_hash(groups, *, annotated=False):
    if annotated:
        values = [(tuple(sorted(g['items'])), g['kind'], tuple(sorted(g['refs']))) for g in groups]
    else:
        values = [tuple(sorted(g['items'])) for g in groups]
    return digest(sorted(values))


def score_run(folder, case, oracle, protocol, *, arm='baseline'):
    paths = {name: folder / (name + '.json') for name in ('request', 'response', 'result')}
    if arm == 'assignment':
        paths['normalized'] = folder / 'normalized.json'
    hashes = {name: file_hash(path) for name, path in paths.items() if path.is_file()}
    model, case_id, repeat = folder.parts[-3:]
    row = {'model': model, 'arm': arm, 'case_id': case_id, 'repeat': repeat, 'files_sha256': hashes}
    binding_errors, value, result, input_bound = [], None, {}, False
    try:
        result = read(paths['result'])
        require(isinstance(result, dict), 'invalid_result_receipt')
    except (OSError, ValueError, TypeError) as exc:
        binding_errors.append(type(exc).__name__ + ':' + str(exc))
        result = {}
    try:
        request = read(paths['request'])
        prompt = protocol['policy'] + '\nSOURCE_JSON:\n' + json.dumps(case['input'], ensure_ascii=False, separators=(',', ':'))
        expected_hash = sha256(prompt.encode()).hexdigest()
        require(request['messages'] == [{'role': 'user', 'content': prompt}],
                'model_input_not_frozen_allowlist')
        for field in ('temperature', 'seed', 'max_tokens', 'cache_prompt', 'reasoning_budget_tokens'):
            require(request[field] == protocol[field], 'generation_config_mismatch:' + field)
        require(request['chat_template_kwargs'] == {'enable_thinking': protocol['thinking']}
                and request['model'] == model, 'generation_template_mismatch')
        require(request.get('stream') is False and digest(request.get('response_format')) == digest({
            'type': 'json_object', 'schema': (assignment_schema if arm == 'assignment' else expected_schema)(len(case['input']['items']))}),
            'output_schema_or_stream_mismatch')
        input_bound = True
        require(result['model'] == model and result['case_id'] == case_id
                and f'repeat-{result["repeat"]}' == repeat, 'run_identity_mismatch')
        require(result['request_sha256'] == hashes['request'], 'request_hash_mismatch')
        require(result['prompt_sha256'] == expected_hash, 'prompt_receipt_mismatch')
        if arm == 'assignment':
            require(result.get('arm') == arm, 'arm_receipt_mismatch')
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        binding_errors.append(type(exc).__name__ + ':' + str(exc))
    try:
        response = read(paths['response'])
        choice = response['choices'][0]
        require(isinstance(choice, dict), 'invalid_response_choice')
        if choice.get('finish_reason') != 'stop':
            binding_errors.append('finish_reason_not_stop')
        value = parse_json(choice['message']['content'])
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        binding_errors.append(type(exc).__name__ + ':' + str(exc))
    if arm == 'assignment':
        assignment_errors, value = normalize_assignments(value, len(case['input']['items']))
        binding_errors.extend(assignment_errors)
        try:
            require(digest(read(paths['normalized'])) == digest(value), 'normalized_assignment_mismatch')
        except (OSError, ValueError, TypeError) as exc:
            binding_errors.append(type(exc).__name__ + ':' + str(exc))
    errors, groups, coverage = validate(value, oracle['ids'])
    valid = result.get('valid') is True and not binding_errors and not errors
    seconds = result.get('seconds')
    seconds = seconds if type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0 else None
    diagnostic = score_groups(groups, oracle)
    row.update(valid=valid, runner_valid=result.get('valid'), runner_errors=result.get('errors'),
        independent_errors=binding_errors + errors, input_bound_to_frozen_protocol=input_bound,
        result_present='result' in hashes, coverage=coverage, seconds=seconds,
        usage=result.get('usage'), timings=result.get('timings'), reasoning_characters=result.get('reasoning_characters'),
        groups_count=result.get('groups_count'), quality=diagnostic if valid else None,
        partial_diagnostic=None if valid else diagnostic,
        normalized_partition_sha256=partition_hash(groups) if valid else None,
        normalized_annotations_sha256=partition_hash(groups, annotated=True) if valid else None)
    return row


def consistency(rows, field):
    counts = Counter(row[field] for row in rows if row['valid'])
    n = sum(counts.values())
    return {'valid_repeats': n, 'unique_hashes': len(counts), 'hash_counts': dict(counts),
            'all_equal': len(counts) == 1 if n >= 2 else None,
            'equal_repeat_pair_fraction': sum(math.comb(count, 2) for count in counts.values()) / math.comb(n, 2) if n >= 2 else None}


def aggregate(rows, cases, models, repeats):
    output = []
    for model in models:
        for case_id in cases:
            selected = [r for r in rows if r['model'] == model and r['case_id'] == case_id]
            valid = [r for r in selected if r['valid']]
            medians = {}
            for field in ('primary_pairwise', 'all_pairwise', 'metadata_classification', 'gold_exact_groups',
                          'major_section_starts', 'markdown_boundaries'):
                values = [r['quality'][field]['f1'] for r in valid if field in r['quality']]
                if values:
                    medians[field + '_f1'] = statistics.median(values)
            for scope in ('main', 'supplementary', 'micro'):
                values = [r['quality']['figure_links'][scope]['f1'] for r in valid]
                if values:
                    medians['figure_links_' + scope + '_f1'] = statistics.median(values)
            all_times = [r['seconds'] for r in selected if r['seconds'] is not None]
            valid_times = [r['seconds'] for r in valid if r['seconds'] is not None]
            output.append({'model': model, 'case_id': case_id, 'expected_repeats': repeats,
                'observed_runs': len(selected), 'valid_runs': len(valid),
                'valid_fraction_observed': len(valid) / len(selected) if selected else None,
                'valid_fraction_planned': len(valid) / repeats,
                'missing_repeats': [n for n in range(1, repeats + 1) if not any(r['repeat'] == f'repeat-{n}' for r in selected)],
                'valid_only_score_medians': medians,
                'primary_pairwise_f1_planned_invalid_missing_zero': sum(r['quality']['primary_pairwise']['f1'] for r in valid) / repeats,
                'markdown_exact_partition_successes': sum(r['quality'].get('markdown_partition_exact', False) for r in valid)
                    if cases[case_id]['input']['format'] == 'markdown' else None,
                'markdown_policy_successes': sum(r['quality'].get('markdown_partition_exact', False)
                    and r['quality'].get('markdown_nonsection_kind_count') == 0 for r in valid)
                    if cases[case_id]['input']['format'] == 'markdown' else None,
                'seconds_median_all_observed': statistics.median(all_times) if all_times else None,
                'seconds_median_valid_only': statistics.median(valid_times) if valid_times else None,
                'partition_consistency': consistency(selected, 'normalized_partition_sha256'),
                'annotation_consistency': consistency(selected, 'normalized_annotations_sha256')})
    return output


def self_check(root):
    cases, oracles, _, _, _ = load_oracles(root)
    count = 0
    for key, oracle in oracles.items():
        def response(members):
            groups = []
            for group in members:
                refs = set().union(*(oracle['item_refs'][i] for i in group))
                groups.append({'kind': 'metadata' if group == oracle['metadata'] else 'section',
                    'items': sorted(group), 'figure_refs': [{'scope': s, 'number': n} for s, n in sorted(refs)]})
            return {'groups': groups}
        value = response(oracle['groups'])
        errors, groups, coverage = validate(value, oracle['ids'])
        require(not errors and coverage['exactly_once'] == len(oracle['ids']), 'selfcheck_valid_oracle')
        score = score_groups(groups, oracle)
        require(score['primary_pairwise']['f1'] == score['gold_exact_groups']['f1'] == 1, 'selfcheck_gold_scores')
        require(score['figure_links']['micro']['f1'] == 1, 'selfcheck_gold_links')
        require(partition_hash(groups) == partition_hash(list(reversed(groups))), 'selfcheck_order_independence')
        invalid = response(oracle['groups'])
        invalid['groups'][0]['items'].append(invalid['groups'][0]['items'][0])
        require('duplicate_ids' in validate(invalid, oracle['ids'])[0], 'selfcheck_duplicates')
        invalid = response(oracle['groups'])
        invalid['groups'][0]['items'][0] = True
        require(validate(invalid, oracle['ids'])[0], 'selfcheck_bool_is_not_id')
        if oracle['format'] == 'paper':
            weak = response([oracle['metadata']] + [{i} for i in sorted(oracle['primary'])])
            errors, weak_groups, _ = validate(weak, oracle['ids'])
            result = score_groups(weak_groups, oracle)
            require(not errors and result['primary_pairwise']['f1'] == 0
                    and abs(result['all_pairwise']['f1'] - .9734239802224969) < 1e-12, 'selfcheck_metadata_dominance')
            invalid = response(oracle['groups'])
            invalid['groups'][0]['items'] = []
            errors, partial, coverage = validate(invalid, oracle['ids'])
            require(errors and coverage['missing_ids'] and score_groups(partial, oracle)['gold_exact_groups']['fn'] > 0,
                    'selfcheck_missing_not_dropped')
        else:
            require(score['markdown_boundaries']['f1'] == 1, 'selfcheck_markdown_boundaries')
            _, merged, _ = validate(response([oracle['ids']]), oracle['ids'])
            require(score_groups(merged, oracle)['markdown_boundaries']['fn'] > 0, 'selfcheck_merged_headings')
            sections = oracle['groups']
            disconnected = response([sections[0] | sections[-1]] + sections[1:-1])
            _, disconnected_groups, _ = validate(disconnected, oracle['ids'])
            disconnected_score = score_groups(disconnected_groups, oracle)
            require(disconnected_score['markdown_boundaries']['f1'] == 1
                    and not disconnected_score['markdown_partition_exact']
                    and disconnected_score['primary_pairwise']['f1'] < 1
                    and disconnected_score['markdown_noncontiguous_group_indices'], 'selfcheck_disconnected_merge')
            groups[0]['refs'].add(('main', 999))
            require(score_groups(groups, oracle)['figure_links']['main']['fp'] == 1, 'selfcheck_invented_figure')
        count += 1
    request_counts = {}
    for directory, schema in (('runs', expected_schema), ('assignment-runs', assignment_schema)):
        request_counts[directory] = 0
        for path in sorted((root / directory).glob('*/*/repeat-*/request.json')):
            case_id = path.parent.parent.name
            require(case_id in cases, 'selfcheck_unknown_request_case')
            request = read(path)  # Request structure only; never inspect response quality.
            expected = {'type': 'json_object', 'schema': schema(len(cases[case_id]['input']['items']))}
            require(digest(request.get('response_format')) == digest(expected)
                    and request.get('stream') is False, 'selfcheck_saved_request_schema:' + str(path))
            request_counts[directory] += 1
    print(json.dumps({'self_check': 'passed', 'oracle_cases': count,
                      'saved_request_schemas_checked': request_counts,
                      'models_called': 0, 'files_written': 0}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('output/t03-context-models'))
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--models', nargs='+', help='Planned model roster; include models not yet run.')
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if args.self_check:
        self_check(root)
        return
    destination = root / 'metrics.json'
    require(not destination.exists(), 'metrics_already_exists')
    cases, oracles, protocol, paths, hashes = load_oracles(root)
    arms = {'baseline': {'directory': 'runs', 'protocol': protocol, 'cases': cases}}
    assignment_path = root / 'assignment-protocol.json'
    if assignment_path.exists():
        paths['assignment_protocol'] = assignment_path
        hashes['assignment_protocol'] = file_hash(assignment_path)
        assignment = read(assignment_path)
        require(assignment['cases_sha256'] == hashes['cases']
                and sha256(assignment['policy'].encode()).hexdigest() == assignment['policy_sha256'],
                'assignment_protocol_binding_mismatch')
        require(type(assignment['repeats']) is int and assignment['repeats'] > 0
                and assignment['case_ids'] == ['Test_Paper'], 'assignment_scope_mismatch')
        arms['assignment'] = {'directory': 'assignment-runs', 'protocol': assignment,
                              'cases': {key: cases[key] for key in assignment['case_ids']}}
    else:
        require(not (root / 'assignment-runs').exists(), 'assignment_runs_without_protocol')
    discovered = {path.name for arm in arms.values() for path in (root / arm['directory']).glob('*') if path.is_dir()}
    models = sorted(set(args.models)) if args.models else sorted(discovered)
    require(models and discovered <= set(models), 'no_models_or_unplanned_model')
    require(all(re.fullmatch(r'[A-Za-z0-9_.-]+', model) and model not in ('.', '..') for model in models), 'invalid_model_label')
    rows, summaries, run_hashes = [], [], {}
    for arm_name, arm in arms.items():
        arm_rows = []
        for model in models:
            for folder in sorted((root / arm['directory'] / model).glob('*/repeat-*')):
                if not folder.is_dir():
                    continue
                case_id = folder.parent.name
                require(case_id in arm['cases'] and re.fullmatch(r'repeat-[1-9][0-9]*', folder.name), 'unexpected_run')
                require(int(folder.name.split('-')[1]) <= arm['protocol']['repeats'], 'repeat_outside_frozen_protocol')
                row = score_run(folder, cases[case_id], oracles[case_id], arm['protocol'], arm=arm_name)
                arm_rows.append(row)
                for name, value in row['files_sha256'].items():
                    run_hashes[str((folder / (name + '.json')).relative_to(root))] = value
        rows.extend(arm_rows)
        summaries.extend({'arm': arm_name, **summary} for summary in
                         aggregate(arm_rows, arm['cases'], models, arm['protocol']['repeats']))
    report = {'schema_version': 'context-grouping-metrics-v1',
        'state': 'partial' if any(s['missing_repeats'] for s in summaries) or any(not r['result_present'] for r in rows)
                 else 'complete_for_planned_models' if args.models else 'complete_for_discovered_models',
        'scope': 'Reviewed Test_Paper reference agreement and synthetic Markdown diagnostics; not semantic truth.',
        'expected_model_roster': 'Explicit --models roster.' if args.models else 'Models discovered under either arm; no undiscovered model is claimed complete.',
        'oracle_file_sha256': hashes, 'run_file_sha256': run_hashes, 'scorer_sha256': file_hash(__file__),
        'definitions': {'pairwise': 'Unordered same-group pairs; paper primary universe is fixed gold103, not model-selected.',
            'metadata_bias': 'Gold metadata126 owns7875 positive pairs; primary103 owns430.',
            'partial_diagnostic': 'Invalid runs have quality=null; diagnostics keep missing IDs and exclude multiply-owned IDs from predicted groups.',
            'figure_links': 'Per-predicted-group union of frozen explicit source references/definitions. Main/supp namespaces separate; not per-mention attribution or asset resolution.',
            'empty_metric': 'No gold or predicted positives: precision/recall null, F1=1 for correct absence. Scope macro excludes zero-gold scopes.',
            'figure_membership': 'Best F1 overlap of each reviewed Figure body+caption+panel group; one predicted group may be selected for several Figures.',
            'hashes': 'Partition hash ignores group order/kind/refs; annotation hash additionally includes kind and distinct refs.',
            'markdown': 'Boundary score is diagnostic: disconnected section merges can keep identical boundaries. Exact partition and primary pairwise detect them; policy success also requires kind=section. Hierarchy/Setext syntax are not exercised by these fixtures.',
            'assignment_arm': 'Separate follow-up changes both fixed-key output representation and explicit subsection instruction. Raw assignment keys/labels are independently validated and normalized.json must match exactly. Not a causal isolation of schema alone.',
            'timing': 'Runner seconds; all-observed and valid-only medians reported separately. Usage is retained runner metadata, not scorer token estimates.'},
        'models': models, 'case_ids': list(cases),
        'arms': {name: {'case_ids': list(arm['cases']), 'repeats': arm['protocol']['repeats']} for name, arm in arms.items()},
        'runs': rows, 'aggregates': summaries,
        'model_calls': 0, 'database_calls': 0, 'existing_source_writes': 0}
    require(all(file_hash(paths[key]) == value for key, value in hashes.items()), 'oracle_changed_during_scoring')
    require(all(file_hash(root / name) == value for name, value in run_hashes.items()), 'run_changed_during_scoring')
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'state': report['state'], 'runs': len(rows), 'valid_runs': sum(r['valid'] for r in rows),
                      'metrics': str(destination), 'sha256': file_hash(destination)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
