"""Local source-preserving D2I worker: Docker storage and an explicit PDF parser.

MinerU image200 OCR + Pro high is the default; earlier parsers remain selectable.
Assembly and verification are scripts, without semantic Generator/Validator calls.
Resume uses the frozen parser bundle and durable Compiler Runtime stages.
"""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import subprocess
import sys
from uuid import uuid4

from palimpsest.source_units import SOURCE_UNITS_VERSION
from palimpsest.d2i import SOURCE_GROUPS_VERSION
from palimpsest.information import SOURCE_SCHEMA_VERSION
from palimpsest.errors import PalimpsestError
from palimpsest.hybrid_profile import (HYBRID_PARSER, DUAL_PARSER, IMAGE_PARSER,
                                     matches_hybrid_parser, matches_dual_parser, matches_image_parser)


ROOT = Path(__file__).resolve().parents[1]
HYBRID_OPTIONS = ('mineru-hybrid', 'mineru-hybrid-dual', 'mineru-hybrid-native')


def event(kind, **fields):
    print(json.dumps({'event':kind,**fields},ensure_ascii=False),flush=True)


def command(arguments, *, body=None, timeout=120):
    result = subprocess.run(arguments, input=None if body is None else json.dumps(body,ensure_ascii=False),
                            capture_output=True, text=True,encoding='utf-8',cwd=ROOT,timeout=timeout)
    if result.returncode:
        if result.returncode==7:
            try:
                if json.loads(result.stdout.splitlines()[-1]).get('command_status')=='succeeded':
                    return result.stdout
            except (ValueError,IndexError,AttributeError):
                pass
        # Display only safe machine error codes, never raw provider/DSN logs.
        try:
            error = json.loads(result.stdout.splitlines()[-1])['error']['code']
        except (ValueError,KeyError,IndexError,TypeError):
            error = 'worker_command_failed'
        raise PalimpsestError(error,'Worker command failed.',4)
    return result.stdout


class Worker:
    def __init__(self,args):
        self.args=args
        self.work=args.work_dir.resolve()
        if not self.work.is_relative_to(ROOT) or self.work == ROOT:
            raise PalimpsestError('invalid_work_directory','Use a dedicated directory within the repository.',2)
        self.work.mkdir(parents=True,exist_ok=True)
        self.job_id=None
        self.claim=None
        self.claimed=False
        if args.parser != 'mineru' and (args.reuse_parser_job or args.figure_inventory):
            raise PalimpsestError('unsupported_figure_repair',
                                  'Legacy pipeline Figure repair requires --parser mineru.',2)
        if bool(args.reuse_parser_job) != bool(args.figure_inventory):
            raise PalimpsestError('figure_repair_input_required','Figure repair requires a retained parser job and reviewed inventory.',2)

    def app(self,*arguments,body=None):
        if self.claim is not None and self.claim.poll() is not None:
            raise PalimpsestError('worker_claim_lost','Execution ownership was lost.',6)
        raw = command(['docker','compose','-p',self.args.project,'run','--rm','--no-deps','-T',
                       '--volume',f'{self.work.as_posix()}:/exchange',
                       'app',*arguments,'--json'],body=body)
        return json.loads(raw.splitlines()[-1])['result']

    def profile(self):
        image_id=command(['docker','image','inspect','--format','{{.Id}}',self.args.parser_image]).strip()
        self.selected_parser_image=image_id
        if self.args.parser in HYBRID_OPTIONS and image_id != HYBRID_PARSER['image_digest']:
            raise PalimpsestError('parser_profile_mismatch','The selected Hybrid image differs from the verified runtime.',4)
        manifest_command=['docker','run','--rm','--network','none','--volume',
                          f'{self.args.models_volume}:/models:ro','--entrypoint']
        if self.args.parser == 'mineru':
            raw=command([*manifest_command,'cat',image_id,'/models/manifest.json'])
            model_manifest=json.loads(raw)
            manifest_hash=sha256(raw.encode()).hexdigest()
        else:
            # Hash bytes in the container before Windows text-mode newline conversion.
            raw=command([*manifest_command,'python',image_id,'-c',
                         'import hashlib,json; from pathlib import Path; '
                         'raw=Path("/models/manifest.json").read_bytes(); '
                         'print(json.dumps({"manifest":json.loads(raw),'
                         '"sha256":hashlib.sha256(raw).hexdigest()}))'])
            manifest_receipt=json.loads(raw)
            model_manifest=manifest_receipt['manifest']
            manifest_hash=manifest_receipt['sha256']
        profile={'schema_version':'source-d2i-v1','parser':{
            'provider':'mineru','version':'3.4.5','backend':'pipeline','image_digest':image_id,
            'models_manifest_sha256':manifest_hash,
            'model_manifest':model_manifest,'device':'cuda','gpu_uuid':self.args.gpu,
            'method':'auto','language':'ch','formula':True,'table':True,
            'network':'none','adapter_version':'mineru-middle-v2'},
            'transformation':{'algorithm':(SOURCE_GROUPS_VERSION if self.args.information_layout == 'groups'
                                         else SOURCE_UNITS_VERSION),'schema_version':SOURCE_SCHEMA_VERSION},
            'policy':{'version':'source-d2i-v1','llm_calls':0,
                      'source_fidelity':'source_preserving','extraction_scope':'whole_document',
                      'implementation_sha256':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                          'src/palimpsest/mineru_adapter.py','src/palimpsest/information.py',
                          'src/palimpsest/d2i.py','src/palimpsest/source_units.py',
                          'src/palimpsest/compiler_runtime.py','src/palimpsest/figure_adapter.py',
                          'src/palimpsest/figure_coverage.py','deploy/mineru/run_parser.py')}}}
        if self.args.parser == 'paddleocr-vl':
            profile['parser']={
                'provider':'paddleocr-vl','version':'3.7.0','backend':'transformers',
                'pipeline_version':'v1.6','image_digest':image_id,
                'models_manifest_sha256':manifest_hash,'model_manifest':model_manifest,
                'device':'cuda','gpu_uuid':self.args.gpu,'network':'none',
                'adapter_version':'paddleocr-raw-v1'}
            profile['policy']['implementation_sha256']={
                name:sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                    'src/palimpsest/paddle_adapter.py','src/palimpsest/information.py',
                    'src/palimpsest/d2i.py','src/palimpsest/source_units.py',
                    'src/palimpsest/compiler_runtime.py','deploy/paddleocr/run_parser.py')}
        elif self.args.parser in HYBRID_OPTIONS:
            raw=command(['docker','run','--rm','--network','none','--volume',
                         f'{self.args.pipeline_models_volume}:/pipeline-models:ro','--entrypoint',
                         'python',image_id,'-c',
                         'import hashlib,json; from pathlib import Path; '
                         'raw=Path("/pipeline-models/manifest.json").read_bytes(); '
                         'print(json.dumps({"manifest":json.loads(raw),'
                         '"sha256":hashlib.sha256(raw).hexdigest()}))'])
            pipeline_receipt=json.loads(raw)
            runner='deploy/mineru-hybrid/run_parser.py'
            dual = self.args.parser == 'mineru-hybrid-dual'
            image = self.args.parser == 'mineru-hybrid'
            profile['parser']={**(IMAGE_PARSER if image else DUAL_PARSER if dual else HYBRID_PARSER),
                'models_manifest_sha256':manifest_hash,'model_manifest':model_manifest,
                'pipeline_models_manifest_sha256':pipeline_receipt['sha256'],
                'pipeline_model_manifest':pipeline_receipt['manifest'],
                'gpu_uuid':self.args.gpu,'runner_sha256':sha256((ROOT/runner).read_bytes()).hexdigest()}
            profile['policy']['implementation_sha256']={
                name:sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                    'src/palimpsest/mineru_adapter.py','src/palimpsest/information.py',
                    'src/palimpsest/d2i.py','src/palimpsest/source_units.py',
                    'src/palimpsest/compiler_runtime.py','src/palimpsest/hybrid_profile.py',runner)}
            if dual or image:
                profile['parser']['renderer_sha256'] = sha256((ROOT/'src/palimpsest/pdf_raster.py').read_bytes()).hexdigest()
                profile['policy']['implementation_sha256'].update({
                    name:sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                        'src/palimpsest/pdf_raster.py', 'src/palimpsest/pdf_raster_adapter.py',
                        'src/palimpsest/hybrid_receipt.py')})
                mode_files = (('src/palimpsest/image_adapter.py',) if image else
                              ('src/palimpsest/dual_adapter.py', 'src/palimpsest/transcription_selection.py'))
                profile['policy']['implementation_sha256'].update({
                    name:sha256((ROOT/name).read_bytes()).hexdigest() for name in mode_files})
            matcher = matches_image_parser if image else matches_dual_parser if dual else matches_hybrid_parser
            if not matcher(profile['parser']):
                raise PalimpsestError('parser_profile_mismatch','The selected Hybrid model profile differs from the verified runtime.',4)
        if self.args.reuse_parser_job:
            source=self.app('jobs','show',self.args.reuse_parser_job,'--include-input')
            if (source['data_id']!=self.args.data_id or not source.get('parse')
                    or self.args.generation<=source['generation']):
                raise PalimpsestError('invalid_parser_reuse','Use the same Data and an explicit later repair generation.',2)
            if source['profile']['parser']!=profile['parser']:
                raise PalimpsestError('parser_profile_mismatch','Retained parser profile does not match the selected runtime.',4)
            inventory=self.args.figure_inventory.resolve(strict=True)
            if not inventory.is_relative_to(ROOT) or self.args.figure_inventory.is_symlink():
                raise PalimpsestError('unsafe_path','Use a reviewed Figure inventory within this repository.',2)
            profile['policy'].update({
                'figure_inventory_sha256':sha256(inventory.read_bytes()).hexdigest(),
                'figure_inventory_origin':'reviewed_original_pdf_regions',
                'extraction_scope':'whole_document',
                'reused_parser_job_id':source['execution_id'],
                'reused_parser_manifest_sha256':source['parse']['manifest_hash']})
        if self.args.information_layout == 'groups':
            profile['policy']['implementation_sha256'].update({
                name:sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                    'src/palimpsest/source_groups.py', 'src/palimpsest/section_projection.py',
                    'src/palimpsest/figure_references.py')})
        path=self.work/'profile.json'
        path.write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf-8')
        return profile

    def parser_command(self, parser_output, parser_name):
        runner={'mineru':'deploy/mineru/run_parser.py',
                'mineru-hybrid':'deploy/mineru-hybrid/run_parser.py',
                'mineru-hybrid-dual':'deploy/mineru-hybrid/run_parser.py',
                'mineru-hybrid-native':'deploy/mineru-hybrid/run_parser.py',
                'paddleocr-vl':'deploy/paddleocr/run_parser.py'}[self.args.parser]
        arguments=['docker','run','--rm','--name',parser_name,'--network','none','--gpus','all',
                   '--env',f'CUDA_VISIBLE_DEVICES={self.args.gpu}',
                   '--volume',f'{self.args.project}_artifacts:/data:ro',
                   '--volume',f'{self.args.models_volume}:/models:ro',
                   '--volume',f'{self.work.as_posix()}:/work',
                   '--volume',f'{(ROOT/runner).as_posix()}:/run_parser.py:ro']
        if self.args.parser in HYBRID_OPTIONS:
            arguments.extend(['--volume',f'{self.args.pipeline_models_volume}:/pipeline-models:ro'])
        if self.args.parser in ('mineru-hybrid', 'mineru-hybrid-dual'):
            arguments.extend(['--volume',f'{(ROOT/'src').as_posix()}:/runtime:ro',
                              '--env','PYTHONPATH=/runtime','--env','PYTHONDONTWRITEBYTECODE=1'])
        arguments.extend(['--entrypoint','python',self.selected_parser_image,'/run_parser.py'])
        if self.args.parser == 'mineru':
            arguments.extend(['--data-id',self.args.data_id])
        else:
            arguments.extend(['--input',f'/data/objects/sha256/{self.args.data_id[:2]}/{self.args.data_id}',
                              '--document',self.args.data_id,'--models-dir','/models'])
        if self.args.parser in HYBRID_OPTIONS:
            arguments.extend(['--image-digest',self.selected_parser_image])
        arguments.extend(['--profile','/work/profile.json',
                          '--output','/work/'+parser_output.relative_to(self.work).as_posix()])
        return arguments

    def run(self):
        self.profile()
        started=self.app('compile','data',self.args.data_id,'--profile','/exchange/profile.json',
                         '--generation',str(self.args.generation))
        self.job_id=started['execution_id']
        (self.work/'job.json').write_text(json.dumps(started,indent=2),encoding='utf-8')
        event('job',**started)
        self.claim=subprocess.Popen(['docker','compose','-p',self.args.project,'run','--rm','--no-deps','-T',
                                     'app','jobs','hold',self.job_id,'--json'],
                                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                    text=True,encoding='utf-8',cwd=ROOT)
        try:
            ack=json.loads(self.claim.stdout.readline())
            if (ack.get('result') or {}).get('state')!='claimed':
                raise PalimpsestError('job_busy','Another worker owns this execution.',6)
            self.claimed=True
            return self.continue_job()
        except BaseException as error:
            code=error.code if isinstance(error,PalimpsestError) else (
                'interrupted' if isinstance(error,KeyboardInterrupt) else 'worker_failure')
            if self.claimed and self.claim.poll() is None and code not in ('job_busy','worker_claim_lost'):
                try:
                    self.app('jobs','fail',self.job_id,'--code',code)
                except (PalimpsestError,OSError,subprocess.SubprocessError):
                    event('failure_record_unavailable',execution_id=self.job_id)
            raise
        finally:
            try:
                self.claim.stdin.close()
            except BrokenPipeError:
                pass
            try:
                self.claim.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.claim.terminate()
            self.claim=None
            self.claimed=False

    def finish(self,job):
        information=self.app('information','list','--data-id',self.args.data_id)
        information['information']=[row for row in information['information'] if row['information_id'] in job['information_ids']]
        (self.work/'job_result.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
        (self.work/'information.json').write_text(json.dumps(information,ensure_ascii=False,indent=2),encoding='utf-8')
        event('finished',execution_id=self.job_id,state=job['state'],information_count=len(job['information_ids']))
        return 7 if job['state']=='needs_human' else 0

    def continue_job(self):
        job=self.app('jobs','show',self.job_id,'--include-input')
        if job['state'] in ('completed','zero_output','needs_human'):
            return self.finish(self.app('jobs','show',self.job_id))
        if job['state']=='failed':
            self.app('jobs','retry',self.job_id)
            job=self.app('jobs','show',self.job_id,'--include-input')
        if job['state']=='prepared' and self.args.reuse_parser_job:
            # Export verifies retained CAS bytes; the original parse is immutable.
            source=self.app('jobs','show',self.args.reuse_parser_job,'--include-input')
            if (source['data_id']!=self.args.data_id or source['parse']['manifest_hash']
                    !=job['profile']['policy']['reused_parser_manifest_sha256']):
                raise PalimpsestError('parser_reuse_changed','Retained parser identity changed.',4)
            target=self.work/'parser-reuse'/self.job_id
            exported=self.app('jobs','export-parser',self.args.reuse_parser_job,
                              '--directory','/exchange/'+target.relative_to(self.work).as_posix())
            inventory_path=self.args.figure_inventory.resolve(strict=True)
            raw=inventory_path.read_bytes()
            if sha256(raw).hexdigest()!=job['profile']['policy']['figure_inventory_sha256']:
                raise PalimpsestError('figure_inventory_changed','The reviewed inventory changed after profile selection.',4)
            inventory=json.loads(raw)
            for figure in inventory['figures']:
                relative=figure['image']['path']
                parts=PurePosixPath(relative).parts
                if ('\\' in relative or ':' in relative or not parts or parts[0]!='images'
                        or any(p in ('','.','..') for p in relative.split('/'))):
                    raise PalimpsestError('unsafe_path','Figure image paths must be under inventory images/.',4)
                original=inventory_path.parent.joinpath(*parts).resolve(strict=True)
                if not original.is_relative_to(inventory_path.parent):
                    raise PalimpsestError('unsafe_path','Figure image escapes its inventory.',4)
                content=original.read_bytes()
                if (sha256(content).hexdigest()!=figure['image']['sha256']
                        or len(content)!=figure['image']['byte_size']):
                    raise PalimpsestError('integrity_conflict','Figure image does not match the reviewed inventory.',4)
                destination=target.joinpath(*parts)
                destination.parent.mkdir(parents=True,exist_ok=True)
                if destination.exists() and destination.read_bytes()!=content:
                    raise PalimpsestError('export_conflict','A retained artifact must not be overwritten.',6)
                destination.write_bytes(content)
            (target/'palimpsest_figures.json').write_bytes(raw)
            self.app('jobs','parsed',self.job_id,'--directory','/exchange/'+target.relative_to(self.work).as_posix(),
                     '--middle',exported['middle'],'--expected-pages',str(len(source['parse']['bundle']['pages'])))
            event('parser_reused',execution_id=self.job_id,source_execution_id=source['execution_id'])
            job=self.app('jobs','show',self.job_id,'--include-input')
        if job['state']=='prepared':
            parser_output=self.work/'parser'/self.job_id/(str(job['attempt'])+'-'+uuid4().hex)
            # A prior attempt may have crashed before posting its complete receipt.
            # A new attempt gets a distinct directory; published parser blobs remain intact.
            result_file=parser_output/'parse_result.json'
            if not result_file.exists():
                event('parsing_started',execution_id=self.job_id)
                parser_name='palimpsest-parser-'+uuid4().hex
                try:
                    # Long documents may take hours; cancellation still cleans up below.
                    command(self.parser_command(parser_output,parser_name),timeout=None)
                finally:
                    # The daemon can outlive a timed-out Docker client. Only remove
                    # the unique container this invocation explicitly created.
                    subprocess.run(['docker','rm','--force',parser_name],capture_output=True,timeout=30)
            parsed=json.loads(result_file.read_text(encoding='utf-8'))
            profile=json.loads((self.work/'profile.json').read_text(encoding='utf-8'))
            profile_hash=sha256(json.dumps(profile,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
            if parsed['data_id']!=self.args.data_id or parsed.get('compilation_profile_sha256')!=profile_hash:
                raise PalimpsestError('parser_data_mismatch','Wrong parser input.',4)
            middle=Path(parsed['middle_relative_path'])
            relative_directory=(parser_output.relative_to(self.work)/middle.parent).as_posix()
            self.app('jobs','parsed',self.job_id,'--directory',f'/exchange/{relative_directory}',
                     '--middle',middle.name,'--expected-pages',str(parsed['page_count']))
            job=self.app('jobs','show',self.job_id,'--include-input')
        image_root=self.work/'restored'/self.job_id
        self.app('jobs','export-parser',self.job_id,'--directory','/exchange/'+image_root.relative_to(self.work).as_posix())
        if job['state'] in ('parsed','proposed'):
            event('source_materialization_started',execution_id=self.job_id,llm_calls=0)
            self.app('jobs','materialize',self.job_id)
        return self.finish(self.app('jobs','show',self.job_id))


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-id',required=True)
    parser.add_argument('--project',default='palimpsest-dev')
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--generation',type=int,default=1)
    parser.add_argument('--parser',choices=(*HYBRID_OPTIONS,'paddleocr-vl','mineru'),default='mineru-hybrid',
                        help='PDF default: original PDF rendered at 200 DPI, then MinerU Pro high OCR. No automatic fallback.')
    parser.add_argument('--information-layout', choices=('groups', 'blocks'), default='groups',
                        help='Store script-grouped I by default; blocks explicitly retains the historical layout.')
    parser.add_argument('--parser-image',help='Docker image; defaults to the selected parser image.')
    parser.add_argument('--models-volume',
                        help='Docker volume or absolute model directory, mounted read-only at /models.')
    parser.add_argument('--pipeline-models-volume',default='palimpsest-t03-mineru-models',
                        help='Existing pipeline models, mounted read-only at /pipeline-models for Hybrid.')
    parser.add_argument('--gpu',help='One CUDA GPU UUID; defaults to the selected parser trial GPU.')
    parser.add_argument('--reuse-parser-job',help='Reuse an exact retained parser for an explicit later source conversion generation.')
    parser.add_argument('--figure-inventory',type=Path,help='Reviewed palimpsest_figures.json and its source-region images.')
    args=parser.parse_args(argv)
    if args.parser_image is None:
        args.parser_image={'mineru-hybrid':'palimpsest-mineru-hybrid:3.4.5-pro2605',
                           'mineru-hybrid-dual':'palimpsest-mineru-hybrid:3.4.5-pro2605',
                           'mineru-hybrid-native':'palimpsest-mineru-hybrid:3.4.5-pro2605',
                           'paddleocr-vl':'palimpsest-paddleocr:3.7.0-vl1.6',
                           'mineru':'palimpsest-mineru:3.4.5'}[args.parser]
    if args.models_volume is None:
        args.models_volume={'mineru-hybrid':(ROOT/'output/t03-mineru-hybrid-pro/models').as_posix(),
                            'mineru-hybrid-dual':(ROOT/'output/t03-mineru-hybrid-pro/models').as_posix(),
                            'mineru-hybrid-native':(ROOT/'output/t03-mineru-hybrid-pro/models').as_posix(),
                            'paddleocr-vl':(ROOT/'output/t03-paddleocr-vl16/models').as_posix(),
                            'mineru':'palimpsest-t03-mineru-models'}[args.parser]
    if args.gpu is None:
        args.gpu=('GPU-ae1e4ffa-2dba-7ba3-f9f7-1bae0ab26f57' if args.parser in HYBRID_OPTIONS
                  else 'GPU-9fbbd689-092e-9dc9-cf2e-a6b51f66dcf8')
    return args


def main():
    args=parse_args()
    worker=None
    try:
        worker=Worker(args)
        return worker.run()
    except (PalimpsestError,subprocess.SubprocessError,OSError,ValueError,KeyError,KeyboardInterrupt) as error:
        code=error.code if isinstance(error,PalimpsestError) else ('interrupted' if isinstance(error,KeyboardInterrupt) else 'worker_failure')
        details=error.details if isinstance(error,PalimpsestError) else {}
        event('failed',execution_id=worker.job_id if worker else None,error_code=code,
              validation_rule=details.get('validation_rule'),candidate_index=details.get('candidate_index'))
        return error.exit_code if isinstance(error,PalimpsestError) else 4


if __name__=='__main__':
    raise SystemExit(main())
