"""Additional frozen Q8 evaluation; reuse the original policy and HTTP runner."""
import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import statistics

from run_script_context_review import (
    POLICY, MODEL, read, digest, save, make_draft, make_packets, normalized,
    run_packet, local_request, apply, validate_decisions, schema,
)


def prepare_document(root, paper):
    source = root / 'corpus' / paper / 'evidence' / 'source_bundle.json'
    visual = source.parent / 'visuals' / 'manifest.json'
    bundle = read(source)
    blocks = bundle['blocks']
    if bundle['profile']['adapter_version'] != 'mineru-hybrid-image200-v1':
        raise ValueError('parser_profile')
    if len({b['block_id'] for b in blocks}) != len(blocks):
        raise ValueError('duplicate_source_block')
    # Match the page projection: stable MinerU reading index within original page.
    blocks = sorted(blocks, key=lambda b: (b['page_index'], b['upstream_metadata']['index']))
    rows = [{'id': n, 'block_id': b['block_id'], 'page_number': b['page_index'] + 1,
             'source_type': b['type'], 'content': b['text'],
             'content_sha256': hashlib.sha256(b['text'].encode()).hexdigest(),
             'bbox': b['bbox'], 'raw_locator': b['raw_locator'],
             'anchor_sha256': b['anchor_sha256']} for n, b in enumerate(blocks)]
    target = root / 'documents' / paper
    source_map = {'data_id': bundle['data_id'], 'items': rows,
         'pages': bundle['pages'], 'source_bundle_sha256': digest(source),
         'identity': 'document-local experiment aliases; no canonical Information IDs'}
    if (target / 'source.json').exists():
        if read(target / 'source.json') != source_map:
            raise ValueError('existing_source_map_changed')
    else:
        save(target / 'source.json', source_map)
    draft = make_draft(rows, read(visual))
    packets = make_packets(draft, rows)
    for packet in packets:
        packet['packet_id'] = paper + '-' + packet['packet_id']
    save(target / 'draft.json', draft)
    save(target / 'packets.json', packets)
    print(json.dumps({'paper': paper, 'pages': len(bundle['pages']), 'sources': len(rows),
          'groups': len(draft['groups']), 'packets': len(packets),
          'issues': sum(len(p['issues']) for p in packets)}), flush=True)


def check_cases(cases, oracle, root):
    if len({p['packet_id'] for p in cases}) != len(cases):
        raise ValueError('duplicate_case')
    if set(oracle) != {p['packet_id'] for p in cases}:
        raise ValueError('oracle_case_coverage')
    for packet in cases:
        expected = oracle[packet['packet_id']]
        if len(packet['issues']) != 1:
            raise ValueError('challenge_requires_one_issue')
        key, issue = next(iter(packet['issues'].items()))
        if expected['decision'] not in issue['options']:
            raise ValueError('oracle_decision')
        ids = {s['id'] for s in packet['source']}
        if (len(ids) != len(packet['source']) or ids != set(packet['source_ids'])
                or not set(issue['source_ids']) <= ids):
            raise ValueError('invisible_source')
        rows = read(root / 'documents' / expected['paper'] / 'source.json')['items']
        for source in packet['source']:
            if type(source['id']) is not int or not 0 <= source['id'] < len(rows):
                raise ValueError('invalid_source_alias')
            if source != {k: rows[source['id']][k] for k in ('id', 'page_number', 'source_type', 'content')}:
                raise ValueError('changed_source')
        if not issue['target_ids'] or not set(issue['target_ids']) <= set(issue['source_ids']):
            raise ValueError('invisible_target')
        conditions = expected['evidence_all_of_any']
        if not conditions or any(not v or not set(v) <= set(issue['source_ids']) for v in conditions):
            raise ValueError('invalid_evidence_oracle')
        if not any(len(set(pick)) + (not set(pick).intersection(issue['target_ids'])) <= 4
                   for pick in product(*conditions)):
            raise ValueError('impossible_evidence_oracle')
        if not expected['reason_codes'] or not expected['rationale']:
            raise ValueError('missing_oracle_rationale')
        if not set(expected['reason_codes']) <= set(schema(packet)['properties'][key]['properties']['reason_code']['enum']):
            raise ValueError('oracle_reason_enum')


def freeze(root):
    cases = read(root / 'challenge/packets.json')
    check_cases(cases, read(root / 'oracle/expected.json'), root)
    names = ['run_extended_context_review.py', 'run_script_context_review.py',
             'run_title_experiment.py', 'run_context_grouping_experiment.py',
             'run_context_assignment_experiment.py', 'score_script_context_review.py',
             'score_context_grouping_experiment.py']
    for name in names:
        target = root / 'frozen' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as f:
            f.write(Path(__file__).with_name(name).read_bytes())
    paths = [p for folder in ('documents', 'challenge', 'oracle', 'frozen')
             for p in sorted((root / folder).rglob('*')) if p.is_file()]
    paths.append(root / 'runtime.ps1')
    (root / 'runs').mkdir(exist_ok=True)
    (root / 'final').mkdir(exist_ok=True)
    save(root / 'protocol.json', {
        'model': MODEL, 'policy': POLICY, 'temperature': 0, 'seed': 42,
        'context_size': 32768, 'max_tokens': 4096, 'reasoning_budget_tokens': 2048,
        'text_only': True, 'canonical_writes': 0,
        'natural_repeats': 1, 'challenge_repeats': 3,
        'papers': ['paper02', 'paper04', 'paper05'],
        'challenge_order': [p['packet_id'] for p in cases],
        'artifact_hashes': {p.relative_to(root).as_posix(): digest(p) for p in paths},
        'oracle_sent_to_model': False,
        'scope': 'full-paper draft diagnostic once; balanced candidate decisions three times',
    })


def run(root, mode):
    protocol = read(root / 'protocol.json')
    for name, sha in protocol['artifact_hashes'].items():
        if digest(root / name) != sha:
            raise ValueError('frozen_input_changed:' + name)
    save(root / 'runs' / (mode + '-health.json'), local_request('/health'))
    save(root / 'runs' / (mode + '-props.json'), local_request('/props'))
    if mode == 'natural':
        for paper in protocol['papers']:
            doc = root / 'documents' / paper
            packets = read(doc / 'packets.json')
            decisions = {p['packet_id']: run_packet(root, p, 1, protocol) for p in packets}
            if all(v is not None for v in decisions.values()):
                try:
                    result = apply(read(doc / 'draft.json'), packets, decisions, read(doc / 'source.json')['items'])
                    save(root / 'final' / paper / 'projection.json', result)
                    save(root / 'final' / paper / 'normalized.json', normalized(result['groups']))
                except Exception as exc:
                    save(root / 'final' / paper / 'failure.json', {'application_error': type(exc).__name__ + ':' + str(exc)})
            else:
                save(root / 'final' / paper / 'failure.json', {'failed_packets': [k for k, v in decisions.items() if v is None]})
    elif mode == 'challenge':
        for repeat in range(1, protocol['challenge_repeats'] + 1):
            for packet in read(root / 'challenge/packets.json'):
                run_packet(root, packet, repeat, protocol)
    else:
        run_packet(root, read(root / 'challenge/regression.json'), 1, protocol)


def score_one(value, packet, expected):
    validate_decisions(value, packet)
    answer = value[next(iter(packet['issues']))]
    evidence = set(answer['evidence_ids'])
    return {'action_correct': answer['decision'] == expected['decision'],
            'evidence_sufficient': all(evidence & set(group) for group in expected['evidence_all_of_any']),
            'reason_appropriate': answer['reason_code'] in expected['reason_codes']}


def score(root):
    from score_script_context_review import read_packet_run, replay, reason_diagnostics
    protocol = read(root / 'protocol.json')
    # A missing receipt is an unfinished experiment, not a scored model failure.
    scheduled = [(p, repeat) for p in read(root / 'challenge/packets.json')
                 for repeat in range(1, protocol['challenge_repeats'] + 1)]
    scheduled += [(p, 1) for paper in protocol['papers']
                  for p in read(root / 'documents' / paper / 'packets.json')]
    scheduled.append((read(root / 'challenge/regression.json'), 1))
    for packet, repeat in scheduled:
        folder = root / 'runs' / packet['packet_id'] / f'repeat-{repeat}'
        result = read(folder / 'result.json')
        if (type(result.get('valid')) is not bool or not isinstance(result.get('errors'), list)
                or result['valid'] != (not result['errors'])):
            raise ValueError('nonterminal_result_receipt')
        read(folder / 'request.json')
        if result['valid']:
            read(folder / 'response.json')
            read(folder / 'decisions.json')
    for paper in protocol['papers']:
        final = root / 'final' / paper
        if (final / 'failure.json').exists():
            failure = read(final / 'failure.json')
            if set(failure) == {'failed_packets'}:
                packets = read(root / 'documents' / paper / 'packets.json')
                failed = [p['packet_id'] for p in packets if not read(
                    root / 'runs' / p['packet_id'] / 'repeat-1/result.json')['valid']]
                if not failed or failure['failed_packets'] != failed:
                    raise ValueError('invalid_failure_receipt')
            elif set(failure) != {'application_error'} or not isinstance(failure['application_error'], str) or not failure['application_error']:
                raise ValueError('invalid_failure_receipt')
        else:
            read(final / 'projection.json')
            read(final / 'normalized.json')
    hashes = {str((root / 'protocol.json').resolve()): digest(root / 'protocol.json')}
    for name, sha in protocol['artifact_hashes'].items():
        if digest(root / name) != sha:
            raise ValueError('frozen_input_changed:' + name)
        hashes[str((root / name).resolve())] = sha
    calls, cases, natural = [], [], []
    expected = read(root / 'oracle/expected.json')
    for packet in read(root / 'challenge/packets.json'):
        trial = []
        for repeat in range(1, protocol['challenge_repeats'] + 1):
            receipt, value = read_packet_run(root, packet, repeat, protocol, hashes)
            calls.append({'arm': 'challenge', **receipt})
            flags = score_one(value, packet, expected[packet['packet_id']]) if value else {
                'action_correct': False, 'evidence_sufficient': False, 'reason_appropriate': False}
            trial.append({'repeat': repeat, 'valid': receipt['valid'], **flags, 'response': value})
        answers = [t['response'] for t in trial]
        actions = [next(iter(a.values()))['decision'] if a else None for a in answers]
        cases.append({'packet_id': packet['packet_id'], 'expected': expected[packet['packet_id']],
                      'trials': trial, 'stable_action': None not in actions and len(set(actions)) == 1,
                      'stable_response': None not in answers and all(a == answers[0] for a in answers)})
    for paper in protocol['papers']:
        doc = root / 'documents' / paper
        packets, rows = read(doc / 'packets.json'), read(doc / 'source.json')['items']
        decisions = {}
        for packet in packets:
            receipt, value = read_packet_run(root, packet, 1, protocol, hashes)
            calls.append({'arm': 'natural', 'paper': paper, **receipt})
            decisions[packet['packet_id']] = value
        row = {'paper': paper, 'sources': len(rows), 'pages': len(read(doc / 'source.json')['pages']),
               'draft_groups': len(read(doc / 'draft.json')['groups']), 'packets': len(packets),
               'issues': sum(len(p['issues']) for p in packets), 'complete_projection': False}
        row['reviewed_source_count'] = len({i for p in packets for i in p['source_ids']})
        row['target_source_count'] = len({i for p in packets for issue in p['issues'].values() for i in issue['target_ids']})
        row['unreviewed_source_count'] = len(rows) - row['reviewed_source_count']
        try:
            if any(v is None for v in decisions.values()) or (root / 'final' / paper / 'failure.json').exists():
                raise ValueError('failed_run_or_application')
            projection = read(root / 'final' / paper / 'projection.json')
            packed = read(root / 'final' / paper / 'normalized.json')
            if projection != replay(read(doc / 'draft.json'), packets, decisions, rows):
                raise ValueError('projection_replay_mismatch')
            if packed != normalized(projection['groups']):
                raise ValueError('projection_normalized_mismatch')
            coverage = Counter(i for g in projection['groups'] for i in g['items'])
            if coverage != Counter(range(len(rows))):
                raise ValueError('projection_source_coverage')
            row.update(complete_projection=True, final_groups=len(projection['groups']),
                       unresolved=projection['unresolved'],
                       figures_without_body_context=[f['number'] for f in projection['figures'] if not f['context_groups']],
                       figures_without_panel_members=[f['number'] for f in projection['figures'] if not f['source_figure']['member_panel_ids']],
                       actions=dict(Counter(v['decision'] for v in projection['ledger'])),
                       reason_diagnostics=reason_diagnostics(packets, decisions))
            for name in ('projection', 'normalized'):
                path = root / 'final' / paper / (name + '.json')
                hashes[str(path.resolve())] = digest(path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row['error'] = type(exc).__name__ + ':' + str(exc)
        natural.append(row)
    packet = read(root / 'challenge/regression.json')
    receipt, value = read_packet_run(root, packet, 1, protocol, hashes)
    calls.append({'arm': 'regression', **receipt})
    regression = {'valid': receipt['valid'], 'response': value,
                  'expected': read(root / 'oracle/regression-expected.json')}
    regression['correct'] = sum(value and value[k]['decision'] == action or False
                                for k, action in regression['expected'].items())
    trials = [t for case in cases for t in case['trials']]
    summary = {name: sum(t[name] for t in trials) for name in
               ('valid', 'action_correct', 'evidence_sufficient', 'reason_appropriate')}
    summary.update(unique_cases=len(cases), trials=len(trials),
                   joint_action_and_evidence=sum(t['action_correct'] and t['evidence_sufficient'] for t in trials),
                   cases_all_actions_correct=sum(all(t['action_correct'] for t in c['trials']) for c in cases),
                   stable_actions=sum(c['stable_action'] for c in cases),
                   stable_responses=sum(c['stable_response'] for c in cases))
    timing = {}
    for arm in ('natural', 'challenge', 'regression'):
        selected = [c for c in calls if c['arm'] == arm]
        seconds = [c['seconds'] for c in selected if c['seconds'] is not None]
        timing[arm] = {'calls': len(selected), 'seconds': sum(seconds),
                       'median_call_seconds': statistics.median(seconds) if seconds else None,
                       **{k: sum((c['usage'] or {}).get(k, 0) for c in selected)
                          for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}}
    save(root / 'metrics.json', {'summary': summary, 'cases': cases, 'natural': natural,
         'regression': regression, 'timing': timing, 'calls': calls, 'artifact_hashes': hashes,
         'canonical_writes': 0, 'scope': 'candidate review; not general accuracy or K generation'})
    print(json.dumps({'summary': summary, 'timing': timing, 'natural': natural}, ensure_ascii=False), flush=True)


def self_check():
    packet = {'issues': {'x': {'options': ['keep', 'needs_context'], 'source_ids': [0, 1], 'target_ids': [1]}}}
    expected = {'decision': 'needs_context', 'evidence_all_of_any': [[0], [1]], 'reason_codes': ['insufficient_context']}
    value = {'x': {'decision': 'needs_context', 'evidence_ids': [1], 'reason_code': 'insufficient_context'}}
    assert score_one(value, packet, expected) == {'action_correct': True, 'evidence_sufficient': False, 'reason_appropriate': True}
    value['x']['evidence_ids'] = [0, 1]
    assert all(score_one(value, packet, expected).values())
    value['x']['decision'] = 'keep'
    assert not score_one(value, packet, expected)['action_correct']
    value['x']['evidence_ids'] = [0]
    try:
        score_one(value, packet, expected)
    except ValueError:
        pass
    else:
        raise AssertionError('missing target accepted')
    print('4 scoring self-checks passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare-document', 'freeze', 'natural', 'challenge', 'regression', 'score', 'self-check'])
    parser.add_argument('--root', type=Path)
    parser.add_argument('--paper')
    args = parser.parse_args()
    if args.command == 'prepare-document':
        prepare_document(args.root, args.paper)
    elif args.command == 'freeze':
        freeze(args.root)
    elif args.command == 'self-check':
        self_check()
    elif args.command == 'score':
        score(args.root)
    else:
        run(args.root, args.command)
