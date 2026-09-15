"""Drive a prepared propagation run through explicit, leased local model calls.

Canonical authority stays in the Docker CLI. This host controller never reads a
DSN/credential file. Model calls require --allow-model-calls; a bounded --once
invocation reports partial progress, never invented propagation convergence.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from palimpsest.local_glm_provider import PROFILE as MODEL
from palimpsest.data import request_id
from palimpsest.errors import PalimpsestError


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def fail(code, status=6):
    raise PalimpsestError(code, '전파 worker의 실행 범위·lease·보존된 요청을 확인하세요.', status)


def hidden():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def event(state, **values):
    print(json.dumps({'state': state, **values}, ensure_ascii=False), flush=True)


class Journal:
    def __init__(self, directory):
        # A host diagnostic attempt name, not a canonical domain identifier.
        name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + secrets.token_hex(6)
        self.root = (directory.parent / (directory.name + '-controller') / name).resolve()
        if not self.root.is_relative_to(ROOT):
            fail('propagation_journal_outside_repository', 2)
        self.root.mkdir(parents=True, exist_ok=False)
        self.lock, self.serial = threading.Lock(), 0

    def command(self, argv):
        with self.lock:
            self.serial += 1
            path = self.root / f'{self.serial:06d}'
        path.mkdir()
        logged = list(argv)
        for index, value in enumerate(logged[:-1]):
            if value == '--lease-token':
                logged[index + 1] = 'sha256:' + sha256(logged[index + 1].encode()).hexdigest()
        write_json(path / 'command.json', {'argv': logged, 'started_at': datetime.now(timezone.utc).isoformat()})
        return path


def checked_request(directory, container_path):
    value = PurePosixPath(container_path)
    if not value.is_absolute() or not value.is_relative_to('/results') or '..' in value.parts:
        fail('propagation_request_path_outside_workspace')
    path = (directory / str(value.relative_to('/results'))).resolve(strict=True)
    if not path.is_relative_to(directory) or not path.is_file():
        fail('propagation_request_path_outside_workspace')
    request = json.loads(path.read_text(encoding='utf-8'))
    name = request['output_file']
    if (not isinstance(name, str) or not name or name in ('.', '..')
            or Path(name).name != name or '/' in name or '\\' in name):
        fail('propagation_invalid_response_path')
    output = path.parent / name
    if output.is_symlink() or output.with_suffix('.failure.json').is_symlink():
        fail('propagation_invalid_response_path')
    attachments = []
    for image in request['images']:
        image_path = (path.parent / image['path']).resolve(strict=True)
        if not image_path.is_relative_to(directory) or not image_path.is_file():
            fail('propagation_attachment_path_outside_workspace')
        raw = image_path.read_bytes()
        if sha256(raw).hexdigest() != image['sha256']:
            fail('propagation_attachment_changed')
        attachments.append({'sha256': image['sha256'], 'byte_size': len(raw)})
    return path, request, output, attachments


def cached_exchange(output, request, attachments):
    """A response file is reusable only when its exact request/receipt binds it."""
    value = json.loads(output.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or set(value) != {'response', 'receipt'}:
        fail('propagation_cached_exchange_invalid')
    receipt = value['receipt']
    expected_profile = MODEL
    if (not isinstance(receipt, dict) or not isinstance(receipt.get('profile'), dict)
            or receipt.get('actual_delivery') is not True
            or receipt.get('original_pdf_delivered') is not False or not receipt.get('provider_ref')
            or any(receipt.get('profile', {}).get(key) != val for key, val in expected_profile.items())
            or receipt.get('input_sha256') != request['input_sha256']
            or receipt.get('prompt_sha256') != sha256(request['prompt'].encode()).hexdigest()
            or receipt.get('schema_sha256') != digest(request['schema'])
            or receipt.get('output_sha256') != digest(value['response'])
            or receipt.get('image_attachments') != attachments
            or any(receipt.get(key) != request[key] for key in request if key.startswith('delivered_'))):
        fail('propagation_cached_exchange_invalid')
    return value


def stop_owned(process):
    """Stop only this controller's still-running provider worker and descendants."""
    if process is None or process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, **hidden())
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)


class Lease:
    def __init__(self, controller, task, interval=30):
        self.controller, self.task, self.interval = controller, task, interval
        self.stop, self.lost = threading.Event(), threading.Event()
        self.process, self.error_code = None, None
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)

    def renew(self):
        try:
            result = self.controller.app('renew', self.task['task_id'], '--lease-token', self.task['lease_token'],
                '--lease-seconds', str(self.controller.args.lease_seconds))
            if (result.get('state') in ('paused', 'cancelled', 'canceled', 'blocked')
                    or result.get('run_state') in ('paused', 'cancelled', 'canceled', 'blocked')
                    or result.get('lease_token', self.task['lease_token']) != self.task['lease_token']
                    or result.get('task_id', self.task['task_id']) != self.task['task_id']
                    or result.get('owned') is False or result.get('lease_valid') is False):
                fail('propagation_lease_lost')
        except (PalimpsestError, OSError, subprocess.SubprocessError) as error:
            self.error_code = getattr(error, 'code', 'propagation_lease_renew_failed')
            self.lost.set()
            stop_owned(self.process)

    def _heartbeat(self):
        while not self.stop.wait(self.interval):
            self.renew()
            if self.lost.is_set():
                break

    def check(self):
        if self.lost.is_set():
            fail(self.error_code or 'propagation_lease_lost')

    def __enter__(self):
        self.renew()
        self.check()
        self.thread.start()
        return self

    def __exit__(self, kind, value, traceback):
        self.stop.set()
        if kind is not None:
            stop_owned(self.process)
        self.thread.join(timeout=100)


class Controller:
    def __init__(self, args):
        self.args = args
        self.directory = args.directory.resolve()
        if self.directory == ROOT or not self.directory.is_relative_to(ROOT):
            fail('propagation_directory_outside_repository', 2)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.journal, self.active = Journal(self.directory), None

    def app(self, *arguments):
        argv = [self.args.docker, 'compose', '-p', self.args.project, 'run', '--rm', '--no-deps', '-T',
            '--volume', f'{self.directory.as_posix()}:/results',
            '--volume', f'{ROOT.as_posix()}:/repo:ro',
            '--volume', f'{self.args.artifact_volume}:/var/lib/palimpsest/artifacts:ro',
            'app', 'propagation', *arguments, '--directory', '/results',
            '--database-name', self.args.database_name, '--json']
        record = self.journal.command(argv)
        with (record / 'stdout.txt').open('x', encoding='utf-8') as stdout, (record / 'stderr.txt').open('x', encoding='utf-8') as stderr:
            result = subprocess.run(argv, stdout=stdout, stderr=stderr, cwd=ROOT,
                env={**os.environ, 'PALIMPSEST_APP_IMAGE': self.args.app_image},
                timeout=90, check=False, **hidden())
            for stream in (stdout, stderr):
                stream.flush()
                os.fsync(stream.fileno())
        write_json(record / 'finished.json', {'returncode': result.returncode})
        try:
            output = json.loads((record / 'stdout.txt').read_text(encoding='utf-8').splitlines()[-1])
        except (ValueError, IndexError):
            fail('propagation_cli_output_invalid')
        if (not isinstance(output, dict) or not isinstance(output.get('result'), dict)
                or (result.returncode != 0 and output.get('command_status') != 'succeeded')):
            error = output.get('error') if isinstance(output, dict) else None
            fail(error.get('code', 'propagation_cli_failed') if isinstance(error, dict) else 'propagation_cli_failed')
        return output['result']

    def container_path(self, path):
        path = path.resolve(strict=True)
        if not path.is_relative_to(self.directory):
            fail('propagation_exchange_path_outside_workspace')
        return '/results/' + path.relative_to(self.directory).as_posix()

    def interrupted_failure(self, request_path, request, output, attachments, code):
        failure_path = output.with_suffix('.failure.json')
        if not output.exists() and not failure_path.exists():
            write_json(failure_path, {'failure': {'error_code': code, 'diagnostic': {'category': 'transport'},
                'input_sha256': request['input_sha256'], 'prompt_sha256': sha256(request['prompt'].encode()).hexdigest(),
                'schema_sha256': digest(request['schema']),
                'request_file_sha256': sha256(request_path.read_bytes()).hexdigest(),
                'planned_image_attachments': attachments,
                **{key.replace('delivered_', 'planned_', 1): value for key, value in request.items()
                   if key.startswith('delivered_')},
                'actual_delivery': None, 'output_sha256': None}})

    def model_turn(self, task):
        if task.get('operation') not in ('knowledge', 'wiki') or task.get('phase') not in ('generator', 'validator'):
            fail('propagation_invalid_model_task')
        path, request, output, attachments = checked_request(self.directory, task['request_file'])
        failure_path = output.with_suffix('.failure.json')
        with Lease(self, task) as lease:
            if not output.exists() and not failure_path.exists():
                if not self.args.allow_model_calls:
                    return {'state': 'blocked', 'reason': 'model_calls_require_explicit_flag',
                        'request_file': str(path), 'task_id': task['task_id'], 'partial': True}
                argv = [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'tools/run_knowledge_model.py'), str(path)]
                record = self.journal.command(argv)
                try:
                    with (record / 'stdout.txt').open('x', encoding='utf-8') as stdout, (record / 'stderr.txt').open('x', encoding='utf-8') as stderr:
                        options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
                                   if os.name == 'nt' else {'start_new_session': True})
                        lease.process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, cwd=ROOT, **options)
                        while lease.process.poll() is None:
                            lease.check()
                            time.sleep(0.1)
                        for stream in (stdout, stderr):
                            stream.flush()
                            os.fsync(stream.fileno())
                        write_json(record / 'finished.json', {'returncode': lease.process.returncode})
                    lease.check()
                except BaseException:
                    stop_owned(lease.process)
                    self.interrupted_failure(path, request, output, attachments, 'propagation_model_worker_interrupted')
                    raise
                if not output.exists() and not failure_path.exists():
                    self.interrupted_failure(path, request, output, attachments, 'propagation_model_worker_failed')
            lease.renew()
            lease.check()
            if output.exists():
                cached_exchange(output, request, attachments)
                return self.app('accept', task['task_id'], '--lease-token', task['lease_token'],
                    '--phase', task['phase'], '--exchange', self.container_path(output))
            if failure_path.exists():
                failure = json.loads(failure_path.read_text(encoding='utf-8'))['failure']
                if (failure.get('input_sha256') != request['input_sha256']
                        or failure.get('prompt_sha256') != sha256(request['prompt'].encode()).hexdigest()
                        or failure.get('schema_sha256') != digest(request['schema'])):
                    fail('propagation_cached_failure_invalid')
                return self.app('call-failed', task['task_id'], '--lease-token', task['lease_token'],
                    '--phase', task['phase'], '--failure', self.container_path(failure_path))
            fail('propagation_model_output_missing')

    def run(self):
        current = None
        try:
            while True:
                if current is None:
                    current = self.app('next', self.args.run_id, '--lease-seconds', str(self.args.lease_seconds))
                self.active = current
                if current.get('action') == 'model_request':
                    current = self.model_turn(current)
                elif current.get('action') == 'task_completed' or current.get('task_state') == 'done':
                    current = None
                elif current.get('action') == 'blocked' and current.get('task_id'):
                    current = None
                elif current.get('state', current.get('action')) in (
                        'completed', 'paused', 'cancelled', 'canceled', 'blocked', 'needs_human', 'prepared'):
                    return current
                elif current.get('state', current.get('action')) == 'retry_wait':
                    if self.args.once:
                        return {**current, 'partial': True}
                    time.sleep(min(30, max(1, current.get('retry_after_seconds', 5))))
                    current = None
                    continue
                elif current.get('task_id') and current.get('lease_token'):
                    current = self.app('advance', current['task_id'], '--lease-token', current['lease_token'])
                else:
                    if not self.args.once:
                        # Another worker may hold the frontier. This is polling
                        # backpressure, never a semantic completion cutoff.
                        time.sleep(5)
                    current = None
                if self.args.once:
                    return {'state': 'partial', 'partial': True, 'reason': 'one_task_turn_requested',
                            'progress': current}
                if current and current.get('state') in ('completed', 'paused', 'cancelled', 'canceled', 'blocked'):
                    return current
        except KeyboardInterrupt:
            try:
                paused = self.app('pause', self.args.run_id, '--reason', 'Host controller interrupted by its user.')
            except (PalimpsestError, OSError, subprocess.SubprocessError):
                paused = {'state': 'partial', 'reason': 'pause_not_confirmed'}
            return {'state': 'partial', 'partial': True, 'reason': 'user_interrupted', 'pause': paused}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--database-name', required=True)
    parser.add_argument('--artifact-volume', required=True)
    parser.add_argument('--app-image', default='palimpsest-effective-k2k:0.20.0')
    parser.add_argument('--docker', default='docker')
    parser.add_argument('--allow-model-calls', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--lease-seconds', type=int, default=180)
    args = parser.parse_args(argv)
    try:
        args.run_id = request_id(args.run_id)
        if args.lease_seconds < 60:
            fail('propagation_lease_too_short', 2)
        if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.artifact_volume) is None:
            fail('propagation_named_artifact_volume_required', 2)
        controller = Controller(args)
        result = controller.run()
        write_json(controller.journal.root / 'result.json', result)
        event(result.get('state', 'partial'), run_id=args.run_id, journal=str(controller.journal.root),
              reason=result.get('reason'), partial=result.get('state') != 'completed')
        return 0 if result.get('state') == 'completed' else 7
    except (PalimpsestError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        event('partial', run_id=args.run_id, error_code=getattr(error, 'code', 'propagation_controller_failed'), partial=True)
        return getattr(error, 'exit_code', 4)


if __name__ == '__main__':
    sys.exit(main())
