"""Run inside the pinned, network-isolated MinerU image against registered D."""

import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pypdfium2 as pdfium
import torch


def geometry(path):
    with pdfium.PdfDocument(path) as document:
        result=[]
        for index in range(len(document)):
            page=document[index]
            try:
                result.append({'size':list(page.get_size()),'media_box':list(page.get_mediabox()),
                               'crop_box':list(page.get_cropbox()),'rotation':page.get_rotation()})
            finally:
                page.close()
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args()
    if len(args.data_id) != 64 or any(c not in '0123456789abcdef' for c in args.data_id):
        raise ValueError('invalid_data_id')
    source = Path('/data/objects/sha256') / args.data_id[:2] / args.data_id
    if source.is_symlink() or sha256(source.read_bytes()).hexdigest() != args.data_id:
        raise ValueError('data_integrity_failed')
    if importlib.metadata.version('mineru') != '3.4.5' or not torch.cuda.is_available():
        raise ValueError('parser_profile_unavailable')
    if torch.cuda.device_count()!=1:
        raise ValueError('parser_gpu_selection_ambiguous')
    args.output.mkdir(parents=True,exist_ok=True)
    if list(args.output.glob('**/*_middle.json')):
        raise ValueError('parser_output_already_exists')
    with tempfile.TemporaryDirectory(prefix='palim-source-') as temporary:
        pdf_path = Path(temporary) / 'source.pdf'
        shutil.copyfile(source,pdf_path)
        if sha256(pdf_path.read_bytes()).hexdigest() != args.data_id:
            raise ValueError('data_integrity_failed')
        pages = geometry(pdf_path)
        command = ['mineru','-p',str(pdf_path),'-o',str(args.output),'-b','pipeline',
                   '-m','auto','-l','ch','-f','true','-t','true']
        environment = dict(os.environ, MINERU_MODEL_SOURCE='local', MINERU_DEVICE_MODE='cuda',
                           MINERU_TOOLS_CONFIG_JSON='/models/mineru.json',
                           HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        with (args.output/'mineru.log').open('w',encoding='utf-8') as log:
            completed = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if completed.returncode:
            raise RuntimeError('mineru_execution_failed')
    outputs = list(args.output.glob('**/*_middle.json'))
    if len(outputs) != 1:
        raise ValueError('ambiguous_parser_output')
    middle_path = outputs[0]
    middle = json.loads(middle_path.read_text(encoding='utf-8'))
    actual_pages = middle.get('pdf_info',[])
    if [p.get('page_idx') for p in actual_pages] != list(range(len(pages))):
        raise ValueError('partial_parser_output')
    origins=list(middle_path.parent.glob('*_origin.pdf'))
    if len(origins)!=1:
        raise ValueError('parser_origin_missing')
    origin_pages=geometry(origins[0])
    if len(origin_pages)!=len(pages):
        raise ValueError('parser_origin_page_mismatch')
    for original, reserialized in zip(pages,origin_pages):
        if original['rotation']!=reserialized['rotation']:
            raise ValueError('parser_origin_rotation_changed')
        for key in ('size','media_box','crop_box'):
            if any(abs(a-b)>0.03 for a,b in zip(original[key],reserialized[key])):
                raise ValueError('parser_origin_box_changed')
    for original, parsed in zip(pages,actual_pages):
        size = parsed.get('page_size',[])
        # MinerU rounds page sizes to integer points. Record the observed transform
        # and permit only sub-point rounding, never a missing/reordered page.
        if len(size)!=2 or any(abs(float(a)-float(b))>1.0 for a,b in zip(original['size'],size)):
            raise ValueError('parser_geometry_mismatch')
    profile=json.loads(args.profile.read_text(encoding='utf-8'))
    model_hash=sha256(Path('/models/manifest.json').read_bytes()).hexdigest()
    if profile['parser']['models_manifest_sha256']!=model_hash:
        raise ValueError('parser_model_profile_changed')
    profile_hash=sha256(json.dumps(profile,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    result = {'data_id':args.data_id,'page_count':len(pages),'original_pages':pages,
              'parser_origin_pages':origin_pages,'origin_box_tolerance_points':0.03,
              'compilation_profile_sha256':profile_hash,'models_manifest_sha256':model_hash,
              'parser_page_sizes':[p['page_size'] for p in actual_pages],
              'coordinate_system':'top-left PDF points; MinerU integer page-size rounding',
              'geometry_tolerance_points':1.0,'backend':'pipeline','method':'auto','language':'ch',
              'network':'none','device':'cuda','gpu_name':torch.cuda.get_device_name(0),
              'torch_version':torch.__version__,'cuda_version':torch.version.cuda,
              'middle_relative_path':middle_path.relative_to(args.output).as_posix()}
    # Preserve the original-coordinate check in the very same artifact manifest.
    (middle_path.parent/'palimpsest_source_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    receipt=args.output/'parse_result.json'
    temporary_receipt=receipt.with_suffix('.tmp')
    temporary_receipt.write_text(json.dumps(result,indent=2),encoding='utf-8')
    os.replace(temporary_receipt,receipt)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
