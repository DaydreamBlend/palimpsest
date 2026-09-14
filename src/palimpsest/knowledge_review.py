"""Read retained I2K reviews and prepare an explicit continuation of their scope.

This controller does not select important source content, call a provider, or
rebuild Information. Runtime remains the owner of replay, profiles and commits.
"""

from copy import deepcopy

from .data import request_id
from .errors import PalimpsestError

from .i2k_selection import PROFILE as SELECTION_PROFILE
from .multi_source_i2k import PROFILE as MULTI_PROFILE
from . import information_errors

ACCEPTED_DISPOSITIONS = ('accepted_new', 'accepted_revision', 'reused', 'no_material_delta')


def _fail(code):
    raise PalimpsestError(code, '전체 I2K 검토 실행과 보존된 원문 범위를 확인하세요.', 6)


def _scope(job):
    if job['operation'] != 'i2k' or job['profile']['schema_version'] not in (SELECTION_PROFILE, MULTI_PROFILE):
        _fail('knowledge_review_selection_required')
    snapshot = job['input_snapshot']
    packet = snapshot['input']
    ids = [unit['information_id'] for unit in packet['model_input']['information']]
    if (not ids or packet['target_information_ids'] != ids or packet['context_information_ids']
            or packet['excluded_information_ids']):
        _fail('knowledge_review_full_source_required')
    return packet, snapshot.get('data_versions', []), snapshot.get('data_version_mode', 'current')


def _record(record):
    return {key: deepcopy(record.get(key)) for key in (
        'record_id', 'execution_id', 'disposition', 'reason_codes', 'reason',
        'result_node_id', 'result_node_revision_id')} | {
            'candidate_key': (record.get('body') or {}).get('candidate_key')}


def review_status(job):
    """Project stored outcomes, including missing reviews; never infer importance."""
    packet, versions, mode = _scope(job)
    records = {record['record_id']: _record(record) for record in job.get('records', [])}
    generator = {row['information_id']: row for row in job.get('information_reviews', [])}
    validator = {row['information_id']: row for row in job.get('information_review_decisions', [])}
    links = {}
    for row in job.get('information_review_records', []):
        links.setdefault(row['information_id'], []).append(records[row['record_id']])

    source = job.get('source_review') or {}
    manifest = source.get('manifest') or job['input_snapshot'].get('source_review_manifest') or {}
    checked = source.get('validation') or {}
    reviewed_targets = {row['target_id']: row for row in source.get('generator_reviews') or []}
    target_decisions = {row['target_id']: row for row in checked.get('targets', [])}
    item_decisions = {row['item_key']: row for row in checked.get('items', [])}
    bindings = {row['item_key']: row for row in checked.get('bindings', [])}
    pending_targets = set(checked.get('pending_target_ids', []))
    pending_items = set(checked.get('pending_item_keys', []))
    error_policy = job['profile'].get('information_error_policy') == information_errors.POLICY
    targets, items, pending_information = [], [], (information_errors.affected_information_ids(
        job.get('source_requests',[]),job.get('information_review_decisions',[])) if error_policy else set())
    for target in manifest.get('targets', []):
        target_id = target['target_id']
        target_review = reviewed_targets.get(target_id)
        target_decision = target_decisions.get(target_id)
        unresolved = (target_id in pending_targets or target_review is None
                      or target_decision is None or target_decision['verdict'] != 'confirmed')
        for item in (target_review or {}).get('items', []):
            decision = item_decisions.get(item['item_key'])
            bound = bindings.get(item['item_key'], {}).get('records', [])
            item_pending = (item['item_key'] in pending_items or item['disposition'] == 'needs_review'
                            or decision is None or decision['verdict'] != 'confirmed'
                            or len(bound) != len(item['candidate_keys'])
                            or any(record['disposition'] not in ACCEPTED_DISPOSITIONS for record in bound))
            items.append({**deepcopy(item), 'target_id': target_id,
                          'information_id': target['information_id'],
                          'status': 'needs_review' if item_pending else 'reviewed',
                          'validator_review': deepcopy(decision), 'records': deepcopy(bound)})
            if item_pending:
                pending_items.add(item['item_key'])
                unresolved = True
        if unresolved:
            pending_targets.add(target_id)
            pending_information.add(target['information_id'])
        targets.append({**deepcopy(target), 'status': 'needs_review' if unresolved else 'reviewed',
                        'validator_review': deepcopy(target_decision)})

    source_requests = deepcopy(job.get('source_requests', []))
    for source_request in source_requests:
        # A provided source is not a validated review. Runtime keeps a round
        # with source requests unresolved even if bytes have become available.
        pending_information.update(source_request['payload'].get('information_ids', []))
    information = []
    for unit in packet['model_input']['information']:
        identifier = unit['information_id']
        prior, decision = generator.get(identifier), validator.get(identifier)
        linked = links.get(identifier, [])
        unresolved = (identifier in pending_information or prior is None or decision is None
                      or prior['disposition'] == 'needs_review' or decision['verdict'] != 'confirmed'
                      or any(record['disposition'] in ('pending', 'needs_human') for record in linked))
        if unresolved:
            pending_information.add(identifier)
        information.append({'information_id': identifier, 'data_id': unit.get('data_id', packet.get('data_id')),
                            'status': 'needs_review' if unresolved else 'reviewed',
                            'generator_review': deepcopy(prior), 'validator_review': deepcopy(decision),
                            'records': deepcopy(linked)})

    state = job['state']
    if state in ('completed', 'zero_output'):
        action = 'no_work'
    elif state == 'prepared':
        action = 'await_generator'
    elif state == 'proposed':
        action = 'await_validator'
    elif state == 'needs_human' or (state == 'failed' and any(
            call['phase'] == 'generator' and call['status'] == 'failed' for call in job.get('model_calls', []))):
        action = 'resume_review'
    else:
        action = 'inspect_failure'
    if any(call['status'] in ('pending', 'running') for call in job.get('model_calls', [])):
        action = 'await_model_call'
    # Retain the old public status shape for frozen pre-policy executions.
    # The explicit source-issues command can still inspect their actual records.
    error_report = information_errors.report(job) if error_policy else None
    if error_report is not None and error_report['requires_user_review'] and action == 'resume_review':
        action = 'review_d2i_error'
    return {'schema_version': 'knowledge-review-status-v1', 'execution_id': job['execution_id'],
            'request_id': job['request_id'], 'state': state, 'next_action': action,
            'data_id': job['data_id'], 'input_digest': job['input_digest'],
            'generation_complete': (job.get('generator_receipt') or {}).get('generation_complete'),
            'validation_context_sha': job.get('validation_context_sha'),
            'profile': deepcopy(job['profile']),
            'sources': [{'data_id': row['data_id'], 'source_execution_id': row['source_execution_id']}
                        for row in packet.get('sources', [packet])],
            'data_versions': deepcopy(versions), 'data_version_mode': mode,
            'current_data_version_heads': deepcopy(job.get('current_data_version_heads', [])),
            'information': information, 'targets': targets, 'items': items,
            'pending_information_ids': [row['information_id'] for row in information
                                        if row['information_id'] in pending_information],
            'pending_target_ids': [row['target_id'] for row in targets if row['target_id'] in pending_targets],
            'pending_item_keys': [row['item_key'] for row in items if row['item_key'] in pending_items],
            'records': list(records.values()),
            'accepted_knowledge': [row for row in records.values() if row['disposition'] in ACCEPTED_DISPOSITIONS],
            'source_requests': source_requests, 'model_calls': deepcopy(job.get('model_calls', [])),
            'error_code': job.get('error_code'),
            'selection_feedback': deepcopy(job['input_snapshot'].get('selection_feedback')),
            **({'information_errors':error_report} if error_report is not None else {})}


class KnowledgeReview:
    def __init__(self, runtime):
        self.runtime = runtime

    def status(self, execution_id):
        job = self.runtime.show(execution_id)
        result = review_status(job)
        scope = _scope(job)
        history, seen = [], {job['execution_id']}
        feedback = job['input_snapshot'].get('selection_feedback')
        while feedback:
            identifier = feedback['execution_id']
            if identifier in seen:
                _fail('knowledge_review_history_cycle')
            seen.add(identifier)
            prior = self.runtime.show(identifier)
            if _scope(prior) != scope:
                _fail('knowledge_review_scope_changed')
            history.append(review_status(prior))
            feedback = prior['input_snapshot'].get('selection_feedback')
        result['history'] = list(reversed(history))
        return result

    def prepare_resume(self, execution_id, request_id_value):
        """Prepare one review round; a new request ID never means completion.

        The entire original packet and version scope enter Runtime again. Only
        current model/prompt implementation hashes are rebuilt there. Repeating
        the same explicit request is governed by Runtime's atomic replay check.
        """
        identifier = request_id(str(request_id_value))
        job = self.runtime.show(execution_id)
        if job['input_snapshot'].get('revision_target') is not None:
            _fail('knowledge_revision_resume_requires_explicit_target')
        status = review_status(job)
        if status.get('information_errors',{}).get('requires_user_review') or job.get('source_requests'):
            _fail('d2i_information_error_requires_review')
        if status['next_action'] == 'no_work':
            return {'action': 'no_work', 'execution_id': job['execution_id'], 'review': status}
        if status['next_action'] != 'resume_review':
            _fail('knowledge_review_resume_not_ready')
        packet, versions, mode = _scope(job)
        options = {'model_profile': deepcopy(job['profile']['model']), 'selection': True,
                   'feedback_execution_id': job['execution_id']}
        if versions:
            options.update(data_version_ids=[row['version_id'] for row in versions], data_version_mode=mode)
        prepared = self.runtime.prepare('i2k', job['data_id'], identifier, deepcopy(packet), **options)
        return {'action': 'replayed' if prepared.get('replayed') else 'prepared',
                'execution_id': prepared['execution_id'], 'feedback_execution_id': job['execution_id'],
                'job': prepared}

    def prepare_call(self, execution_id, phase, directory, derived_store):
        """Export the exact complete-I request; never invoke a model or D2I."""
        from pathlib import Path
        from .i2k import digest
        from .knowledge_requests import generation_request, validation_request
        from .paper_wiki_runtime import _image_suffix
        from .wiki_projection_store import ProjectionStore

        if phase not in ('generator', 'validator'):
            _fail('invalid_knowledge_phase')
        job = self.runtime.show(execution_id)
        packet, versions, _ = _scope(job)
        output = ProjectionStore(Path(directory))
        with output.locked():
            binding = {'execution_id': job['execution_id'], 'phase': phase,
                       'input_digest': job['input_digest'], 'profile': job['profile']}
            prior = output.read_json(phase + '-binding.json')
            if job['state'] != ('prepared' if phase == 'generator' else 'proposed'):
                _fail('knowledge_call_not_ready')
            assets, images = [], []
            for asset in packet['media_assets']:
                raw = derived_store.read(asset['sha256'], asset['byte_size'])
                path = 'media/' + asset['sha256'] + _image_suffix(raw)
                output.write_bytes(path, raw)
                assets.append({'sha256': asset['sha256'], 'byte_size': asset['byte_size']})
                images.append({'path': path, 'sha256': asset['sha256']})
            context = job if phase == 'generator' else self.runtime.validation_context(job['execution_id'])
            prompt, schema = (generation_request(job['input_snapshot'], assets) if phase == 'generator'
                              else validation_request(context, assets))
            value = {'prompt': prompt, 'schema': schema, 'images': images,
                'input_sha256': job['input_digest'] if phase == 'generator' else context['validation_context_sha'],
                'output_file': phase + '-response.json',
                'delivered_information_ids': packet['target_information_ids']}
            if job['input_snapshot'].get('revision_target') is not None:
                value['delivered_revision_target_id'] = job['input_snapshot']['revision_target']['expected_revision_id']
            if versions:
                value['delivered_data_version_ids'] = [version['version_id'] for version in versions]
            binding['request_sha256'] = digest(value)
            if prior is not None:
                if prior != binding or output.read_json(phase + '-request.json') != value:
                    _fail('knowledge_call_directory_conflict')
                return {'execution_id': job['execution_id'], 'phase': phase,
                    'request_file': str(output.root/(phase + '-request.json')),
                    'request_sha256': digest(value), 'actual_delivery': False, 'replayed': True}
            output.write_json(phase + '-request.json', value)
            output.write_json(phase + '-binding.json', binding)
            return {'execution_id': job['execution_id'], 'phase': phase,
                'request_file': str(output.root/(phase + '-request.json')),
                'request_sha256': digest(value), 'information_count': len(packet['target_information_ids']),
                'actual_delivery': False, 'replayed': False}
