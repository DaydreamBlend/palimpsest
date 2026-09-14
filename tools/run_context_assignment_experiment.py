"""Coverage-constrained follow-up; the model assigns fixed source keys, no rewriting."""
import argparse
import json
from pathlib import Path
import time

from run_context_grouping_experiment import POLICY, KINDS, local_request, sha_text, validate
from run_title_experiment import read, save, digest

ASSIGNMENT_POLICY = '''
OUTPUT REPRESENTATION: Instead of listing source ids inside groups, use assignments
with EVERY fixed source id as a JSON object key, each mapped to one integer group_id.
Define each used group_id exactly once in groups as {group_id,kind,figure_refs}.
Do not put items in group definitions. Every group must have at least one assigned
source record. The application constructs ordered item lists from assignments.
Group ids are temporary labels, not source ids. Reading-context policies above
still apply: retain complete sections, group related Results/Figure evidence,
and preserve all source records. You must actually decide section/subsection
membership, not put the entire Results or Methods into one oversized group.
'''


def assignment_schema(count):
    label = {'type': 'integer', 'minimum': 0, 'maximum': count - 1}
    ref = {'type': 'object', 'properties': {
        'scope': {'type': 'string', 'enum': ['main', 'supplementary']},
        'number': {'type': 'integer', 'minimum': 1}},
        'required': ['scope', 'number'], 'additionalProperties': False}
    group = {'type': 'object', 'properties': {'group_id': label,
        'kind': {'type': 'string', 'enum': KINDS},
        'figure_refs': {'type': 'array', 'items': ref}},
        'required': ['group_id', 'kind', 'figure_refs'], 'additionalProperties': False}
    return {'type': 'object', 'properties': {
        'assignments': {'type': 'object', 'properties': {str(i): label for i in range(count)},
                        'required': [str(i) for i in range(count)], 'additionalProperties': False},
        'groups': {'type': 'array', 'minItems': 1, 'items': group}},
        'required': ['assignments', 'groups'], 'additionalProperties': False}


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('duplicate_json_key:' + key)
        out[key] = value
    return out


def normalize(value, count):
    if not isinstance(value, dict) or set(value) != {'assignments', 'groups'}:
        raise ValueError('invalid_assignment_root')
    assignments, groups = value['assignments'], value['groups']
    if not isinstance(assignments, dict) or set(assignments) != {str(i) for i in range(count)}:
        raise ValueError('assignment_key_coverage')
    if any(type(v) is not int or not 0 <= v < count for v in assignments.values()):
        raise ValueError('invalid_assignment_value')
    if not isinstance(groups, list) or not groups:
        raise ValueError('invalid_group_definitions')
    seen, output = set(), []
    for group in groups:
        if not isinstance(group, dict) or set(group) != {'group_id', 'kind', 'figure_refs'}:
            raise ValueError('invalid_group_definition_fields')
        label = group['group_id']
        if type(label) is not int or not 0 <= label < count or label in seen:
            raise ValueError('invalid_or_duplicate_group_label')
        seen.add(label)
        output.append({'kind': group['kind'], 'items': sorted(int(k) for k, v in assignments.items() if v == label),
                       'figure_refs': group['figure_refs']})
    if seen != set(assignments.values()):
        raise ValueError('unused_or_undefined_group_label')
    out = {'groups': output}
    errors = validate(out, count)
    if errors:
        raise ValueError(';'.join(errors))
    return out


def prepare(root):
    policy = POLICY + ASSIGNMENT_POLICY
    save(root / 'assignment-protocol.json', {
        'policy': policy, 'policy_sha256': sha_text(policy), 'harness_sha256': digest(__file__),
        'base_harness_sha256': digest(Path(__file__).with_name('run_context_grouping_experiment.py')),
        'cases_sha256': digest(root / 'cases.json'), 'case_ids': ['Test_Paper'], 'repeats': 3,
        'temperature': 0, 'seed': 42, 'max_tokens': 8192, 'reasoning_budget_tokens': 2048,
        'context_size': 32768, 'cache_prompt': False, 'thinking': True, 'text_only': True,
        'scope': 'follow-up after baseline failure; schema and explicit subsection instruction changed together'})


def run(root, model):
    protocol = read(root / 'assignment-protocol.json')
    assert digest(__file__) == protocol['harness_sha256']
    assert digest(Path(__file__).with_name('run_context_grouping_experiment.py')) == protocol['base_harness_sha256']
    assert digest(root / 'cases.json') == protocol['cases_sha256']
    base = root / 'assignment-runs' / model
    save(base / 'health.json', local_request('/health'))
    save(base / 'props.json', local_request('/props'))
    case = next(c for c in read(root / 'cases.json')['cases'] if c['case_id'] == 'Test_Paper')
    count = len(case['input']['items'])
    prompt = protocol['policy'] + '\nSOURCE_JSON:\n' + json.dumps(case['input'], ensure_ascii=False, separators=(',', ':'))
    payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0, 'seed': 42, 'max_tokens': 8192, 'stream': False, 'cache_prompt': False,
        'chat_template_kwargs': {'enable_thinking': True}, 'reasoning_budget_tokens': 2048,
        'response_format': {'type': 'json_object', 'schema': assignment_schema(count)}}
    template = local_request('/apply-template', {'messages': payload['messages'],
        'chat_template_kwargs': payload['chat_template_kwargs'], 'add_generation_prompt': True})
    tokens = local_request('/tokenize', {'content': template['prompt'], 'add_special': False})
    token_count = len(tokens['tokens'])
    save(base / 'Test_Paper/preflight.json', {'prompt_sha256': sha_text(prompt),
        'templated_tokens': token_count, 'special_token_margin': 1, 'max_tokens': 8192,
        'context_size': 32768, 'fits': token_count + 1 + 8192 <= 32768})
    if token_count + 1 + 8192 > 32768:
        raise ValueError('context_overflow')
    for repeat in range(1, 4):
        out = base / 'Test_Paper' / f'repeat-{repeat}'
        save(out / 'request.json', payload)
        print(json.dumps({'start': model, 'arm': 'assignment', 'repeat': repeat}), flush=True)
        start = time.perf_counter()
        response, normalized, errors, reasoning_chars = {}, None, [], 0
        try:
            response = local_request('/v1/chat/completions', payload)
            save(out / 'response.json', response)
            choice = response['choices'][0]
            if choice['finish_reason'] != 'stop':
                errors.append('finish_reason:' + str(choice['finish_reason']))
            message = choice['message']
            reasoning_chars = len(message.get('reasoning_content') or '')
            value = json.loads(message['content'], object_pairs_hook=unique_object)
            normalized = normalize(value, count)
            save(out / 'normalized.json', normalized)
        except Exception as exc:
            errors.append(type(exc).__name__ + ':' + str(exc))
        response_metadata = response if isinstance(response, dict) else {}
        result = {'model': model, 'arm': 'assignment', 'case_id': 'Test_Paper', 'repeat': repeat,
            'valid': not errors, 'errors': errors, 'seconds': time.perf_counter() - start,
            'groups_count': len(normalized['groups']) if normalized is not None else None,
            'usage': response_metadata.get('usage'), 'timings': response_metadata.get('timings'),
            'prompt_sha256': sha_text(prompt), 'request_sha256': digest(out / 'request.json'),
            'reasoning_characters': reasoning_chars}
        save(out / 'result.json', result)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['prepare', 'run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--model')
    args = p.parse_args()
    if args.command == 'prepare':
        prepare(args.root)
    elif not args.model:
        p.error('--model required')
    else:
        run(args.root, args.model)
