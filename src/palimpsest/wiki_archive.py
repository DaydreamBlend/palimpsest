"""Validate and preserve a Wiki projection archive without compiling or publishing.

Exact file bytes are the archive; parsed rows are a checked import projection.
Model receipts bind their retained requests, never today's prompt implementation.
"""

from hashlib import sha256
import json
import os
import re

from .artifact_store import _directory
from .data import data_id, request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge_runtime import MODEL
from .multi_source_i2k import combine_packets
from . import paper_wiki as pages


PROFILE = 'paper-topic-wiki-projection-v1'
ARCHIVE_PROFILE = 'wiki-archive-v1'
_UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
_SHA = r'[0-9a-f]{64}'
_JOB_FILES = {'job.json', 'proposal.json', 'validation-context.json', 'decision.json'} | {
    f'{phase}-{suffix}.json' for phase in ('generator', 'validator')
    for suffix in ('request', 'response', 'exchange', 'response.failure')}
_SNAPSHOT_META = {'snapshot_id', 'body_sha256', 'previous_snapshot_id',
                  'previous_snapshot_sha256', 'origin_request_id', 'projection_schema'}


def _fail(code='wiki_archive_integrity'):
    raise PalimpsestError(code, 'Wiki 보관 파일의 원본 bytes·snapshot·출처·판정 연결을 확인하세요.', 6)


def _path_allowed(path):
    if not isinstance(path, str):
        return False
    if path == 'catalog.json':
        return True
    if re.fullmatch(rf'catalogs/{_SHA}\.json|snapshots/{_UUID}\.json', path):
        return True
    match = re.fullmatch(rf'jobs/({_UUID})/(.+)', path)
    return bool(match and (match[2] in _JOB_FILES or re.fullmatch(rf'failures/{_SHA}\.json', match[2])))


def _json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                _fail()
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: _fail())
    if not isinstance(value, dict):
        _fail()
    return value


def _job_input(identifier, job):
    snapshot = job['input_snapshot']
    packet = snapshot['input']
    request = {'source_execution_id': packet['source_execution_id'],
               'metadata': snapshot['metadata'], 'feedback_request_id': job.get('feedback_request_id')}
    notes = (snapshot.get('prior_feedback') or {}).get('review_notes')
    if notes is not None:
        request['review_notes'] = notes
    for name in ('citation_repair', 'editable_item_keys'):
        if snapshot.get(name):
            request[name] = snapshot[name]
    if (job['request_id'] != identifier or job['schema_version'] != PROFILE
            or job['input_digest'] != digest(snapshot) or job['request_sha256'] != digest(request)
            or job['source_data_id'] != packet['data_id']
            or job['source_execution_id'] != packet['source_execution_id']
            or job['metadata'] != snapshot['metadata'] or job.get('review_notes') != notes
            or type(job.get('citation_repair', False)) is not bool
            or type(snapshot.get('citation_repair', False)) is not bool
            or job.get('citation_repair', False) != snapshot.get('citation_repair', False)
            or job.get('editable_item_keys') != snapshot.get('editable_item_keys')
            or job['profile']['schema_version'] != PROFILE
            or job['profile']['model'] != MODEL
            or not job['profile']['implementation']
            or job['state'] not in ('prepared', 'proposed', 'failed', 'needs_review', 'compiled')):
        _fail()
    for value in job['profile']['implementation'].values():
        data_id(value)
    request_id(packet['source_execution_id'])
    data_id(packet['data_id'])
    combine_packets([packet])
    expected = [{k: a[k] for k in ('sha256', 'byte_size')} for a in packet['media_assets']]
    if [{k: a[k] for k in ('sha256', 'byte_size')} for a in job['assets']] != expected:
        _fail()
    for asset in job['assets']:
        if not re.fullmatch(rf'media/{re.escape(asset["sha256"])}\.(png|jpg|webp)', asset['relative_path']):
            _fail('unsafe_path')
    return packet


def _receipt(identifier, job, phase, exchange, parsed, *, required=False):
    request = parsed.get(f'jobs/{identifier}/{phase}-request.json')
    if request is None or not isinstance(exchange, dict) or set(exchange) != {'response', 'receipt'}:
        _fail('wiki_archive_receipt')
    receipt = exchange['receipt']
    packet = job['input_snapshot']['input']
    input_hash = job['input_digest'] if phase == 'generator' else job['validation_context_sha256']
    if (not isinstance(receipt, dict) or not isinstance(receipt.get('profile'), dict)
            or any(receipt['profile'].get(k) != v for k, v in job['profile']['model'].items())
            or receipt.get('actual_delivery') is not True
            or receipt.get('original_pdf_delivered') is not False
            or not isinstance(receipt.get('provider_ref'), str) or not receipt['provider_ref']
            or request['input_sha256'] != input_hash or receipt.get('input_sha256') != input_hash
            or receipt.get('output_sha256') != digest(exchange['response'])
            or receipt.get('prompt_sha256') != sha256(request['prompt'].encode('utf-8')).hexdigest()
            or receipt.get('schema_sha256') != digest(request['schema'])
            or request['delivered_information_ids'] != packet['target_information_ids']
            or receipt.get('delivered_information_ids') != packet['target_information_ids']
            or request['images'] != [{'path': '../../' + a['relative_path'], 'sha256': a['sha256']}
                                     for a in job['assets']]
            or request['output_file'] != phase + '-response.json'
            or receipt.get('image_attachments') != [
                {k: a[k] for k in ('sha256', 'byte_size')} for a in job['assets']]):
        _fail('wiki_archive_receipt')
    response = parsed.get(f'jobs/{identifier}/{phase}-response.json')
    if response is not None and response != exchange:
        _fail('wiki_archive_receipt')
    if required and phase == 'validator':
        generator = parsed[f'jobs/{identifier}/generator-exchange.json']
        if generator['receipt']['provider_ref'] == receipt['provider_ref']:
            _fail('wiki_archive_receipt')


def _validated_proposal(identifier, job, parsed, *, accepted=False):
    base = f'jobs/{identifier}/'
    context, proposal = parsed.get(base + 'validation-context.json'), parsed.get(base + 'proposal.json')
    generator = parsed.get(base + 'generator-exchange.json')
    if (context is None or proposal is None or generator is None
            or digest(context) != job.get('validation_context_sha256')
            or context != {'input_snapshot': job['input_snapshot'], 'proposal': proposal}):
        _fail('wiki_archive_proposal')
    _receipt(identifier, job, 'generator', generator, parsed, required=True)
    snapshot = job['input_snapshot']
    if snapshot.get('citation_repair'):
        proposal_check = pages.normalize_citation_repair(generator['response'], snapshot['input'],
            snapshot['prior_feedback']['proposal'], editable_item_keys=snapshot.get('editable_item_keys'))
    else:
        proposal_check = pages.normalize_proposal(generator['response'], snapshot['input'], snapshot['existing_topics'])
    if proposal_check != proposal:
        _fail('wiki_archive_proposal')
    validator = parsed.get(base + 'validator-exchange.json')
    if accepted or validator is not None:
        if validator is None:
            _fail('wiki_archive_receipt')
        _receipt(identifier, job, 'validator', validator, parsed, required=True)
        decision = pages.validate_decisions(validator['response'], proposal)
        if decision != parsed.get(base + 'decision.json'):
            _fail('wiki_archive_proposal')
        if accepted and (job['state'] != 'compiled' or not proposal['complete'] or not decision['complete']
                or any(x['verdict'] != 'accepted' for x in decision['items'] + decision['topics'])
                or any(x['disposition'] == 'needs_review' for x in proposal['reviews'])):
            _fail('wiki_archive_unaccepted')
    return proposal


def validate_archive_files(files):
    """Validate known exact-byte files; omit orphan snapshots from relational rows.

No source DB lookup or provider call occurs here. Callers must verify canonical
source membership before an archive becomes a queryable DB projection.
"""
    try:
        return _validate(files)
    except PalimpsestError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError, UnicodeError):
        _fail()


def _validate(files):
    if not isinstance(files, dict) or not files or any(
            not _path_allowed(path) or not isinstance(raw, bytes) for path, raw in files.items()):
        _fail('wiki_archive_path')
    parsed = {path: _json(raw) for path, raw in files.items()}
    current = parsed['catalog.json']
    current_sha = digest(current)
    catalogs = {path[9:-5]: value for path, value in parsed.items() if path.startswith('catalogs/')}
    if current_sha not in catalogs or catalogs[current_sha] != current:
        _fail('wiki_archive_catalog')
    jobs = {path.split('/')[1]: value for path, value in parsed.items() if path.endswith('/job.json')}
    all_snapshots = {path[10:-5]: value for path, value in parsed.items() if path.startswith('snapshots/')}
    sources, media = {}, {}
    for identifier, job in jobs.items():
        packet = _job_input(identifier, job)
        base_catalog = catalogs[job['expected_catalog_sha256']]
        if job['input_snapshot']['existing_topics'] != [
                {k: topic[k] for k in ('topic_key', 'title', 'scope')}
                for _, topic in sorted(base_catalog['topics'].items())]:
            _fail('wiki_archive_topic')
        source_id = packet['source_execution_id']
        if source_id in sources and sources[source_id] != packet:
            _fail('wiki_archive_source_changed')
        sources[source_id] = packet
        for asset in job['assets']:
            path = asset['relative_path']
            if path in media and media[path] != asset:
                _fail('wiki_archive_source_changed')
            media[path] = asset
        feedback = job['input_snapshot'].get('prior_feedback')
        if feedback:
            previous = jobs[feedback['request_id']]
            if (feedback['request_id'] != job.get('feedback_request_id')
                    or previous['source_execution_id'] != source_id
                    or feedback['proposal'] != parsed.get(f"jobs/{feedback['request_id']}/proposal.json")
                    or feedback['result'] != parsed.get(f"jobs/{feedback['request_id']}/decision.json")):
                _fail('wiki_archive_proposal')
        if f'jobs/{identifier}/proposal.json' in parsed:
            _validated_proposal(identifier, job, parsed, accepted=job['state'] == 'compiled')
        elif job['state'] in ('proposed', 'needs_review', 'compiled'):
            _fail('wiki_archive_proposal')
        for phase in ('generator', 'validator'):
            response = parsed.get(f'jobs/{identifier}/{phase}-response.json')
            if response is not None:
                _receipt(identifier, job, phase, response, parsed)
    for path, value in parsed.items():
        if path.startswith('jobs/') and path.split('/')[1] not in jobs:
            _fail('wiki_archive_job_missing')
        if '/failures/' in path and digest(value) != path.rsplit('/', 1)[1][:-5]:
            _fail()
    snapshots, visiting = {}, set()
    proposals = {}

    def snapshot(entry):
        identifier = request_id(entry['snapshot_id'])
        value = all_snapshots[identifier]
        if digest(value) != entry['snapshot_sha256']:
            _fail('wiki_archive_snapshot')
        if identifier in visiting:
            _fail('wiki_archive_cycle')
        if identifier in snapshots:
            return value
        visiting.add(identifier)
        if (value['snapshot_id'] != identifier or value['projection_schema'] != PROFILE
                or request_id(value['page_id']) != value['page_id']
                or value['kind'] not in ('paper', 'topic')
                or digest({k: v for k, v in value.items() if k not in _SNAPSHOT_META}) != value['body_sha256']):
            _fail('wiki_archive_snapshot')
        origin = request_id(value['origin_request_id'])
        job = jobs[origin]
        if origin not in proposals:
            proposals[origin] = _validated_proposal(origin, job, parsed, accepted=True)
        proposal = proposals[origin]
        if value['kind'] == 'paper':
            expected = {'page_id': value['page_id'], 'kind': 'paper', 'title': job['metadata']['title'],
                'data_id': job['source_data_id'], 'metadata': job['metadata'],
                'items': proposal['items'], 'topics': proposal['topics'],
                'source_execution_id': job['source_execution_id'],
                'input_sha256': job['input_snapshot']['input']['input_sha256']}
            if job['input_snapshot']['input']['model_input'].get('source_format') == 'code':
                expected['source_format'] = 'code'
            if expected != {k: v for k, v in value.items() if k not in _SNAPSHOT_META}:
                _fail('wiki_archive_proposal')
        elif set(value) - _SNAPSHOT_META != {
                'page_id', 'kind', 'topic_key', 'title', 'scope', 'contributions', 'active'}:
            _fail('wiki_archive_topic')
        previous = value['previous_snapshot_id']
        if previous:
            parent = snapshot({'snapshot_id': previous, 'snapshot_sha256': value['previous_snapshot_sha256']})
            if parent['page_id'] != value['page_id'] or parent['kind'] != value['kind']:
                _fail('wiki_archive_parent')
        elif value['previous_snapshot_sha256'] is not None:
            _fail('wiki_archive_parent')
        snapshots[identifier] = value
        visiting.remove(identifier)
        return value

    versions, identity, selected = {}, {}, set()
    for checksum, catalog in sorted(catalogs.items(), key=lambda pair: pair[1]['version']):
        version = catalog['version']
        if (digest(catalog) != checksum or catalog['schema_version'] != PROFILE
                or set(catalog) != {'schema_version', 'version', 'papers', 'topics', 'commits'}
                or type(version) is not int or version < 0 or version in versions
                or len(catalog['commits']) != version):
            _fail('wiki_archive_catalog')
        versions[version] = checksum
        papers = {}
        for kind in ('papers', 'topics'):
            for key, entry in catalog[kind].items():
                value = snapshot(entry)
                selected.add(entry['snapshot_id'])
                expected_kind = 'paper' if kind == 'papers' else 'topic'
                if (entry['page_id'] != value['page_id'] or entry['body_sha256'] != value['body_sha256']
                        or entry['title'] != value['title'] or value['kind'] != expected_kind
                        or key != value['data_id' if kind == 'papers' else 'topic_key']):
                    _fail('wiki_archive_catalog')
                page_identity = (kind, key)
                if page_identity in identity and identity[page_identity] != value['page_id']:
                    _fail('wiki_archive_page_identity')
                identity[page_identity] = value['page_id']
                if kind == 'papers':
                    papers[key] = value
        if len(set(identity.values())) != len(identity):
            _fail('wiki_archive_page_identity')
        for key, entry in catalog['topics'].items():
            topic = snapshots[entry['snapshot_id']]
            contributions = []
            for owner, paper in sorted(papers.items()):
                items = [item for item in paper['items'] if key in item['topic_keys']]
                if items:
                    contributions.append({'paper_data_id': owner, 'paper_page_id': paper['page_id'],
                                          'paper_title': paper['title'], 'items': items})
                    definition = next(x for x in paper['topics'] if x['topic_key'] == key)
                    if definition != {k: topic[k] for k in ('topic_key', 'title', 'scope')}:
                        _fail('wiki_archive_topic')
            if (topic['contributions'] != contributions or topic['active'] != bool(contributions)
                    or any(entry[k] != topic[k] for k in ('topic_key', 'title', 'scope', 'active'))):
                _fail('wiki_archive_topic')
        if any(t['topic_key'] not in catalog['topics'] for paper in papers.values() for t in paper['topics']):
            _fail('wiki_archive_topic')
        for identifier, receipt in catalog['commits'].items():
            job = jobs[identifier]
            if job['state'] != 'compiled' or receipt != job['result'] or receipt['request_id'] != identifier:
                _fail('wiki_archive_commit')
        if version == 0:
            if catalog['papers'] or catalog['topics'] or catalog['commits']:
                _fail('wiki_archive_catalog')
        else:
            prior_sha = versions[version - 1]
            prior = catalogs[prior_sha]
            if any(catalog['commits'].get(k) != v for k, v in prior['commits'].items()):
                _fail('wiki_archive_commit')
            added = set(catalog['commits']) - set(prior['commits'])
            if len(added) != 1:
                _fail('wiki_archive_commit')
            identifier = added.pop()
            job, receipt = jobs[identifier], catalog['commits'][identifier]
            paper_entry = catalog['papers'][job['source_data_id']]
            if (job['expected_catalog_sha256'] != prior_sha or receipt['catalog_version'] != version
                    or receipt['paper_page_id'] != paper_entry['page_id']
                    or receipt['paper_snapshot_id'] != paper_entry['snapshot_id']
                    or receipt['paper_count'] != len(catalog['papers'])
                    or receipt['topic_count'] != sum(e['active'] for e in catalog['topics'].values())
                    or receipt['canonical_writes'] != 0 or receipt['new_d2i_calls'] != 0):
                _fail('wiki_archive_commit')
            for kind in ('papers', 'topics'):
                if not prior[kind].keys() <= catalog[kind].keys():
                    _fail('wiki_archive_page_identity')
                for key, entry in catalog[kind].items():
                    old = prior[kind].get(key)
                    if old == entry:
                        continue
                    value = snapshots[entry['snapshot_id']]
                    if (value['origin_request_id'] != identifier
                            or value['previous_snapshot_id'] != (old['snapshot_id'] if old else None)
                            or value['previous_snapshot_sha256'] != (old['snapshot_sha256'] if old else None)
                            or (kind == 'papers' and key != job['source_data_id'])):
                        _fail('wiki_archive_commit')
                    if kind == 'topics' and old and any(old[k] != entry[k] for k in ('topic_key', 'title', 'scope')):
                        _fail('wiki_archive_topic')
    if versions[max(versions)] != current_sha:
        _fail('wiki_archive_catalog')
    if snapshots.keys() != selected:
        _fail('wiki_archive_parent')
    if any(job['state'] == 'compiled' and identifier not in current['commits'] for identifier, job in jobs.items()):
        _fail('wiki_archive_commit')
    manifest = {'schema_version': ARCHIVE_PROFILE, 'files': [
        {'path': path, 'sha256': sha256(raw).hexdigest(), 'byte_size': len(raw)}
        for path, raw in sorted(files.items())]}
    return {'files': dict(files), 'manifest': manifest, 'manifest_sha256': digest(manifest),
            'current_catalog_sha256': current_sha, 'catalogs': catalogs, 'snapshots': snapshots,
            'jobs': jobs, 'source_packets': sources, 'media_assets': [media[key] for key in sorted(media)]}


def build_archive(store):
    """Read only known files under no-follow directory descriptors and one lock."""
    def names(relative):
        try:
            with _directory(store.root / relative) as descriptor:
                return sorted(os.listdir(descriptor))
        except FileNotFoundError:
            return []
    with store.locked(), store._store._io_errors():
        paths = ['catalog.json']
        for directory in ('catalogs', 'snapshots'):
            paths.extend(f'{directory}/{name}' for name in names(directory) if name.endswith('.json'))
        for identifier in names('jobs'):
            if re.fullmatch(_UUID, identifier) is None:
                _fail('wiki_archive_path')
            base = 'jobs/' + identifier
            paths.extend(base + '/' + name for name in names(base) if name in _JOB_FILES)
            paths.extend(base + '/failures/' + name for name in names(base + '/failures') if name.endswith('.json'))
        if any(not _path_allowed(path) for path in paths):
            _fail('wiki_archive_path')
        return validate_archive_files({path: store.read_bytes(path) for path in paths})
