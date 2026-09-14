"""Replay a frozen script-review protocol with one alternate local model."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def copy(source, target):
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f:
        f.write(source.read_bytes())


def prepare(root, baseline, model):
    original = read(baseline/'protocol.json')
    copied = {}
    for name in ('source.json','draft.json','draft-normalized.json','packets.json','evaluation_protocol.json',
                 'controls/packet.json','controls/expected.json'):
        copy(baseline/name,root/name)
        copied[name] = digest(root/name)
        assert copied[name] == digest(baseline/name)
    protocol = dict(original)
    protocol['model'] = model
    frozen = dict(original['frozen_hashes'])
    for name, expected in frozen.items():
        source = baseline/'frozen'/name
        assert digest(source) == expected
        copy(source,root/'frozen'/name)
    target = root/'frozen/run_script_context_review.py'
    old = target.read_bytes()
    needle = b"payload = {'model': MODEL, 'messages':"
    replacement = b"payload = {'model': protocol['model'], 'messages':"
    assert old.count(needle) == 1
    # Preserve the copied original before publishing the one-line transport variant.
    target.rename(root/'frozen/run_script_context_review.py.original')
    with target.open('xb') as f:
        f.write(old.replace(needle,replacement))
    frozen['run_script_context_review.py'] = digest(target)
    protocol['frozen_hashes'] = frozen
    save(root/'protocol.json',protocol)
    copy(Path(__file__),root/'frozen'/Path(__file__).name)
    save(root/'comparison-protocol.json',{
        'baseline_root': str(baseline.resolve()), 'model':model,'baseline_model':original['model'],
        'baseline_protocol_sha256':digest(baseline/'protocol.json'),
        'protocol_sha256':digest(root/'protocol.json'), 'copied_artifact_sha256':copied,
        'driver_sha256':digest(__file__),
        'transport_delta':{'before':needle.decode(),'after':replacement.decode(),
                           'baseline_sha256':original['frozen_hashes']['run_script_context_review.py'],
                           'variant_sha256':frozen['run_script_context_review.py']},
        'expected_request_difference':['model'], 'formal_calls':21,'smoke_calls':1,'control_calls':1,
        'scope':'same single-paper frozen draft, policy, candidates, schema and source; alternate model only',
        'controls_expected_not_sent_to_model':True,'canonical_writes':0})
    print(json.dumps({'prepared':True,'model':model,'copied_artifacts':len(copied)}))


def run(root, mode):
    comparison = read(root/'comparison-protocol.json')
    assert digest(__file__) == comparison['driver_sha256']
    assert digest(root/'protocol.json') == comparison['protocol_sha256']
    protocol = read(root/'protocol.json')
    assert protocol['model'] == comparison['model']
    for name, expected in comparison['copied_artifact_sha256'].items():
        assert digest(root/name) == expected
    for name, expected in protocol['frozen_hashes'].items():
        assert digest(root/'frozen'/name) == expected
    sys.path.insert(0,str(root/'frozen'))
    runner = importlib.import_module('run_script_context_review')
    assert Path(runner.__file__).resolve().parent == (root/'frozen').resolve()
    if mode != 'control':
        runner.run(root, mode == 'smoke')
        return
    value = runner.run_packet(root,read(root/'controls/packet.json'),1,protocol,'controls/runs')
    expected = read(root/'controls/expected.json')
    save(root/'controls/evaluation.json',{'valid':value is not None,
        'checks':{key:{'expected':want,'observed':value[key]['decision'] if value else None,
                       'passed':bool(value and value[key]['decision']==want)} for key,want in expected.items()},
        'repeats':1,'scope':'Same two post-hoc sensitivity faults used for 9B; not a held-out success rate',
        'canonical_writes':0})


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['prepare','smoke','run','control'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--baseline',type=Path,default=Path('output/t03-script-context-review'))
    p.add_argument('--model',default='qwen35-4b-q4',choices=['qwen35-4b-q4'])
    args=p.parse_args()
    if args.command=='prepare':prepare(args.root,args.baseline,args.model)
    else:run(args.root,args.command)
