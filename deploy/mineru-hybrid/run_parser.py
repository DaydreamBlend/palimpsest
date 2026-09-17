"""Pinned local MinerU parsing; optional dual transcriptions, no canonical writes."""

import argparse
from hashlib import file_digest
import importlib.metadata as metadata
import json
import math
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import time
from uuid import UUID


PRO_REPO = "opendatalab/MinerU2.5-Pro-2605-1.2B"
PRO_REVISION = "bff20d4ae2bf202df9f45284b4d43681555a97ed"
PRO_WEIGHT_SHA256 = "abf8681ca63b8dec7b67de257af47b821f179442f72998d0696ae2ed9232a5f0"
PIPELINE_MANIFEST_SHA256 = "6e4ab8545ac654440671e551346bd1865d6f12181c7d9f48bfef042c92046408"
PRO_MANIFEST_SHA256 = "919d1cfc207e1dd3a97f9c9cbf3bd6b5c773aac841b8d33176b66bf6d2476f0d"
IMAGE_DIGEST = "sha256:3f9361035fa4d601d54ed524410d89871fe2524047b04a821594485aae93e0d4"
DUAL_ADAPTER_VERSION = "mineru-hybrid-dual200-v1"
IMAGE_ADAPTER_VERSION = "mineru-hybrid-image200-v1"


def digest(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def profile_digest(profile):
    from hashlib import sha256
    return sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def verified_gpu_uuid(torch_uuid, requested_uuid):
    """Torch omits NVIDIA's GPU- prefix; compare the actual 128-bit identity."""
    def canonical(value):
        if not isinstance(value, str):
            raise ValueError("The CUDA GPU UUID is missing or invalid")
        return UUID(value.removeprefix('GPU-'))
    actual = canonical(torch_uuid)
    if actual != canonical(requested_uuid):
        raise ValueError("The visible CUDA GPU does not match the requested profile")
    return 'GPU-' + str(actual)


def validate_profile(profile, source_hash, document, image_digest, runner_hash):
    if document != source_hash or not re.fullmatch('[0-9a-f]{64}', document):
        raise ValueError("The registered Data ID does not match the input PDF")
    expected = {
        'provider':'mineru', 'version':'3.4.5', 'backend':'hybrid-engine',
        'adapter_version':'mineru-hybrid-preproc-v1', 'effort':'high', 'engine':'transformers',
        'image_digest':IMAGE_DIGEST, 'runner_sha256':runner_hash,
        'models_manifest_sha256':PRO_MANIFEST_SHA256,
        'pipeline_models_manifest_sha256':PIPELINE_MANIFEST_SHA256,
        'model_repository':PRO_REPO, 'model_revision':PRO_REVISION,
        'model_weight_sha256':PRO_WEIGHT_SHA256, 'device':'cuda', 'network':'none',
        'method':'auto', 'language':'ch', 'image_analysis':False, 'formula':True, 'table':True,
    }
    parser = profile.get('parser', {})
    if parser.get('adapter_version') == DUAL_ADAPTER_VERSION:
        from palimpsest.hybrid_profile import DUAL_PARSER
        expected.update(DUAL_PARSER)
    elif parser.get('adapter_version') == IMAGE_ADAPTER_VERSION:
        from palimpsest.hybrid_profile import IMAGE_PARSER
        expected.update(IMAGE_PARSER)
    if (profile.get('schema_version') != 'source-d2i-v1' or image_digest != IMAGE_DIGEST
            or any(parser.get(k) != v or type(parser.get(k)) is not type(v) for k, v in expected.items())
            or profile.get('transformation') not in [
                {'algorithm': algorithm, 'schema_version': 'source-information-v1'}
                for algorithm in ('source-units-v1', 'source-groups-v1', 'source-groups-v2')]
            or profile.get('policy', {}).get('llm_calls') != 0
            or profile['policy'].get('source_fidelity') != 'source_preserving'
            or profile['policy'].get('extraction_scope') != 'whole_document'):
        raise ValueError("The requested compilation profile differs from the pinned Hybrid runtime")
    return profile_digest(profile)


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def geometry(path):
    import pypdfium2 as pdfium

    result = []
    with pdfium.PdfDocument(path) as document:
        for index in range(len(document)):
            page = document[index]
            try:
                item = {"page_index": index, "size": list(page.get_size()),
                        "media_box": list(page.get_mediabox()),
                        "crop_box": list(page.get_cropbox()), "rotation": page.get_rotation()}
                if (item["rotation"] != 0 or min(item["size"]) <= 0
                        or not all(math.isfinite(v) for key in ("size", "media_box", "crop_box") for v in item[key])):
                    raise ValueError("Unsupported rotated or invalid original PDF geometry")
                result.append(item)
            finally:
                page.close()
    if not result:
        raise ValueError("The source PDF has no pages")
    return result


def validate_pages(original, parsed, origin):
    if (not isinstance(parsed, list)
            or [p.get("page_idx") for p in parsed] != list(range(len(original)))
            or any(type(p.get("page_idx")) is not int for p in parsed)
            or len(origin) != len(original)):
        raise ValueError("Incomplete or reordered original pages")
    for source, page, copied in zip(original, parsed, origin):
        if source["rotation"] != copied["rotation"]:
            raise ValueError("Parser origin PDF rotation changed")
        for key in ("size", "media_box", "crop_box"):
            if any(abs(a - b) > 0.03 for a, b in zip(source[key], copied[key])):
                raise ValueError("Parser origin PDF geometry changed")
        size = page.get("page_size")
        if (not isinstance(size, list) or len(size) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in size)
                or any(abs(a - b) > 1.0 for a, b in zip(source["size"], size))):
            raise ValueError("Parser page size is outside the recorded integer-rounding tolerance")
        if not isinstance(page.get("preproc_blocks"), list):
            raise ValueError("Every source page must retain preproc_blocks before cross-page merging")


def parse_pdf(source, directory, log_path, *, original, receipt, status_path, secondary=False, image_input=False):
    """Run the same pinned CLI once and retain its untouched SDK artifacts."""
    command = ["mineru", "-p", str(source), "-o", str(directory),
               "-b", "hybrid-engine", "--effort", "high", "--image-analysis", "false",
               "-m", "auto", "-l", "ch", "-f", "true", "-t", "true"]
    prefix = "ocr_" if secondary else ""
    receipt.update(status="running", phase="image200_ocr" if secondary or image_input else "original_pdf_auto")
    receipt[prefix + "command"] = command
    write_json(status_path, receipt)
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, env=os.environ.copy(), stdout=log, stderr=subprocess.STDOUT)
    receipt[prefix + "parser_exit_code"] = completed.returncode
    if completed.returncode:
        raise RuntimeError("MinerU Hybrid execution failed; retained parser log has details")
    if "Using transformers as the inference engine for VLM." not in log_path.read_text(encoding="utf-8"):
        raise ValueError("The actual parser log did not verify the selected Transformers engine")
    paths = {}
    for key, suffix in (("middle", "_middle.json"), ("model", "_model.json"), ("origin", "_origin.pdf")):
        matches = list(directory.rglob("*" + suffix))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one retained {key} artifact")
        paths[key] = matches[0]
    middle = json.loads(paths["middle"].read_text(encoding="utf-8"))
    origin = geometry(paths["origin"])
    validate_pages(original, middle.get("pdf_info"), origin)
    model = json.loads(paths["model"].read_text(encoding="utf-8"))
    if not isinstance(model, list) or len(model) != len(original):
        raise ValueError("Raw Hybrid model output must retain every source page")
    if (secondary or image_input) and (middle.get("_ocr_enable") is not True or middle.get("_effort") != "high"
                      or middle.get("_backend") != "hybrid" or middle.get("_version_name") != "3.4.5"):
        raise ValueError("Image-only input did not activate the pinned Hybrid high OCR route")
    return paths, middle, origin


def render_input(source, directory, *, data_id, page_count, renderer):
    """Use the frozen full-page renderer for either image-only or historical dual parsing."""
    raster = renderer.render_pdf(source, directory)
    if (raster['source']['data_id'] != data_id or raster['source']['page_count'] != page_count
            or raster['renderer']['script_sha256'] != digest(renderer.__file__)):
        raise ValueError("Rasterization changed original Data or its selected renderer")
    derived_pages = [{'page_index':p['derived_page_index'],
                      **{k:p['derived_geometry'][k] for k in ('size','media_box','crop_box','rotation')}}
                     for p in raster['pages']]
    return raster, directory / 'manifest.json', directory / raster['derived_pdf']['path'], derived_pages


def retain_tree(source, target):
    """Copy a complete derived artifact tree and verify exact bytes after copy."""
    if target.exists():
        raise ValueError("A retained artifact directory must not be overwritten")
    files = []
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("A derived artifact tree contains an unexpected symlink")
        if path.is_file():
            files.append((path.relative_to(source), digest(path), path.stat().st_size))
    shutil.copytree(source, target)
    if {p.relative_to(target) for p in target.rglob("*") if p.is_file()} != {p for p, _, _ in files}:
        raise ValueError("Retained artifact inventory changed")
    for relative, expected, size in files:
        copied = target / relative
        if copied.is_symlink() or digest(copied) != expected or copied.stat().st_size != size:
            raise ValueError("Retained runtime/source evidence does not match")


def verify_manifest(path, model_root):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        relative = PurePosixPath(item["path"])
        if (relative.is_absolute() or any(p in ("", ".", "..") for p in item["path"].split("/"))
                or "\\" in item["path"] or ":" in item["path"]):
            raise ValueError("Unsafe model manifest path")
        model_file = model_root.joinpath(*relative.parts)
        if (not model_file.resolve().is_relative_to(model_root.resolve())
                or not model_file.is_file() or digest(model_file) != item["sha256"]
                or model_file.stat().st_size != item["bytes"]):
            raise ValueError("Pinned model artifact mismatch")
    return manifest, digest(path)


def run(args):
    source, output = args.input.resolve(strict=True), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be empty; preserve previous and failed attempts")
    if source.is_relative_to(output):
        raise ValueError("The input PDF must be outside the experiment output")
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    receipt = {"schema_version": "mineru-hybrid-source-v1", "document": args.document,
               "status": "preflight", "completed_pages": 0, "canonical_writes": 0}
    write_json(output / "status.json", receipt)
    try:
        source_hash, runner_hash = digest(source), digest(__file__)
        receipt.update(data_id=source_hash, source_sha256_before=source_hash, runner_sha256=runner_hash)
        profile_bytes = args.profile.read_bytes()
        profile = json.loads(profile_bytes)
        compilation_hash = validate_profile(profile, source_hash, args.document, args.image_digest, runner_hash)
        dual = profile['parser'].get('adapter_version') == DUAL_ADAPTER_VERSION
        image = profile['parser'].get('adapter_version') == IMAGE_ADAPTER_VERSION
        raster_module = None
        if dual or image:
            from palimpsest import pdf_raster as raster_module
            if digest(raster_module.__file__) != profile['parser']['renderer_sha256']:
                raise ValueError("The selected renderer implementation differs from the frozen profile")
            receipt['renderer_sha256'] = profile['parser']['renderer_sha256']
            if dual:
                receipt.update(schema_version="mineru-hybrid-dual-source-v1",
                               transcription_mode="native_plus_image200", native_input_mode="original_pdf_auto",
                               native_input_sha256=source_hash)
            else:
                receipt.update(schema_version="mineru-hybrid-image-source-v1",
                               transcription_mode="image200", input_mode="image_only_pdf")
        receipt.update(compilation_profile_sha256=compilation_hash, image_digest=args.image_digest,
                       adapter_version=profile['parser']['adapter_version'], source_fidelity_verified=False)
        models = args.models_dir.resolve(strict=True)
        pipeline = Path("/pipeline-models")
        pro_manifest, pro_hash = verify_manifest(models / "manifest.json", models / "pro")
        _, pipeline_hash = verify_manifest(pipeline / "manifest.json", pipeline / "pipeline")
        if (pro_manifest.get("repository") != PRO_REPO or pro_manifest.get("revision") != PRO_REVISION
                or digest(models / "pro/model.safetensors") != PRO_WEIGHT_SHA256
                or pro_hash != PRO_MANIFEST_SHA256 or pipeline_hash != PIPELINE_MANIFEST_SHA256):
            raise ValueError("The selected Pro or pipeline model profile changed")
        config_path = output / "mineru.json"
        write_json(config_path, {"config_version": "1.3.2", "models-dir": {
            "pipeline": str(pipeline / "pipeline"), "vlm": str(models / "pro")}})
        environment = {"MINERU_MODEL_SOURCE": "local", "MINERU_DEVICE_MODE": "cuda",
                       "MINERU_TOOLS_CONFIG_JSON": str(config_path), "HF_HUB_OFFLINE": "1",
                       "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
        os.environ.update(environment)
        import torch
        from mineru.utils.engine_utils import get_vlm_engine

        versions = {name: metadata.version(name) for name in (
            "mineru", "mineru-vl-utils", "torch", "torchvision", "transformers", "accelerate", "pypdfium2")}
        if any(versions[k] != v for k, v in {
                "mineru": "3.4.5", "mineru-vl-utils": "1.2.1", "transformers": "4.57.6",
                "accelerate": "1.15.0"}.items()):
            raise ValueError("The pinned parser package versions changed")
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise ValueError("Exactly one CUDA GPU must be selected")
        if any(get_vlm_engine("auto", is_async=mode) != "transformers" for mode in (False, True)):
            raise ValueError("Hybrid must resolve to Transformers; alternate engines are not allowed")
        interfaces = sorted(p.name for p in Path("/sys/class/net").iterdir())
        if interfaces != ["lo"]:
            raise ValueError("Run this parser with Docker --network none")
        torch_gpu_uuid = str(getattr(torch.cuda.get_device_properties(0), "uuid", "unavailable"))
        receipt['torch_gpu_uuid'] = torch_gpu_uuid
        gpu_uuid = verified_gpu_uuid(torch_gpu_uuid, profile['parser'].get('gpu_uuid'))
        original = geometry(source)
        retained_source = output / "source.pdf"
        shutil.copyfile(source, retained_source)
        if digest(retained_source) != source_hash:
            raise ValueError("Retained source PDF does not match its Data hash")
        receipt.update(page_count=len(original), original_pages=original, versions=versions,
                       backend="hybrid-engine", effort="high", resolved_engine="transformers",
                       image_analysis=False, method="auto", language="ch", formula=True, table=True,
                       device="cuda", gpu_name=torch.cuda.get_device_name(0),
                       gpu_uuid=gpu_uuid,
                       gpu_total_memory=torch.cuda.get_device_properties(0).total_memory,
                       cuda_version=torch.version.cuda, torch_runtime_version=torch.__version__,
                       network="none", network_interfaces=interfaces, environment=environment,
                       config_sha256=digest(config_path), pro_models_manifest_sha256=pro_hash,
                       models_manifest_sha256=pro_hash,
                       pipeline_models_manifest_sha256=pipeline_hash,
                       pro_repository=PRO_REPO, pro_revision=PRO_REVISION,
                       pro_weight_sha256=PRO_WEIGHT_SHA256, source_relative_path="source.pdf")
        if image:
            receipt.update(phase="rasterizing_original")
            write_json(output / "status.json", receipt)
            raster_directory = output / "raster"
            raster, raster_manifest, ocr_input, derived_pages = render_input(retained_source, raster_directory,
                data_id=source_hash, page_count=len(original), renderer=raster_module)
            raster_manifest_hash, ocr_input_hash = digest(raster_manifest), raster['derived_pdf']['sha256']
            paths, middle, origin = parse_pdf(ocr_input, output / "parser", output / "mineru.log",
                original=derived_pages, receipt=receipt, status_path=output / "status.json", image_input=True)
            if digest(raster_manifest) != raster_manifest_hash or digest(ocr_input) != ocr_input_hash:
                raise ValueError("The retained raster input changed during OCR")
            raster_module.verify_render(raster_directory, retained_source, check_pixels=False,
                                        expected_script_sha256=receipt['renderer_sha256'])
            receipt.update(raster_manifest_sha256=raster_manifest_hash, ocr_input_sha256=ocr_input_hash,
                           ocr_enable=middle['_ocr_enable'], parser_input_pages=derived_pages)
        else:
            paths, middle, origin = parse_pdf(retained_source, output / "parser", output / "mineru.log",
                original=original, receipt=receipt, status_path=output / "status.json")
        if dual:
            if (type(middle.get('_ocr_enable')) is not bool or middle.get('_effort') != 'high'
                    or middle.get('_backend') != 'hybrid' or middle.get('_version_name') != '3.4.5'):
                raise ValueError("Original-PDF auto parsing must record its actual OCR route")
            receipt.update(native_ocr_enable=middle['_ocr_enable'], phase="rasterizing_original")
            write_json(output / "status.json", receipt)
            raster_directory = output / "raster"
            raster, raster_manifest, ocr_input, derived_pages = render_input(retained_source, raster_directory,
                data_id=source_hash, page_count=len(original), renderer=raster_module)
            raster_manifest_hash = digest(raster_manifest)
            ocr_input_hash = raster['derived_pdf']['sha256']
            ocr_directory = output / "ocr_parser"
            ocr_paths, ocr_middle, ocr_origin = parse_pdf(ocr_input, ocr_directory, output / "mineru_ocr.log",
                original=derived_pages, receipt=receipt, status_path=output / "status.json", secondary=True)
            if digest(raster_manifest) != raster_manifest_hash or digest(ocr_input) != ocr_input_hash:
                raise ValueError("The retained raster input changed during OCR")
            raster_module.verify_render(raster_directory, retained_source, check_pixels=False,
                                        expected_script_sha256=receipt['renderer_sha256'])
            receipt.update(raster_manifest_sha256=raster_manifest_hash, ocr_input_sha256=ocr_input_hash,
                           ocr_enable=ocr_middle['_ocr_enable'], ocr_completed_pages=len(derived_pages),
                           ocr_parser_origin_pages=ocr_origin,
                           ocr_parser_page_sizes=[p['page_size'] for p in ocr_middle['pdf_info']])
        for path, expected in ((source, source_hash), (retained_source, source_hash),
                               (Path(__file__), runner_hash), (config_path, receipt["config_sha256"]),
                               (models / "manifest.json", pro_hash), (pipeline / "manifest.json", pipeline_hash)):
            if digest(path) != expected:
                raise ValueError("Source, runner, model profile, or local configuration changed during parsing")
        if args.profile.read_bytes() != profile_bytes:
            raise ValueError("The compilation profile changed during parsing")
        if (dual or image) and digest(raster_module.__file__) != receipt['renderer_sha256']:
            raise ValueError("The renderer implementation changed during parsing")
        # The existing attach API publishes the middle file's entire directory.
        # Keep byte-exact runtime/source evidence beside the untouched SDK files.
        retained = paths['middle'].parent
        copies = {'source.pdf':retained_source, 'mineru.log':output / 'mineru.log',
                  'mineru.json':config_path, 'palimpsest_profile.json':args.profile,
                  'palimpsest_runner.py':Path(__file__),
                  'palimpsest_pro_models_manifest.json':models / 'manifest.json',
                  'palimpsest_pipeline_models_manifest.json':pipeline / 'manifest.json'}
        if dual or image:
            copies['palimpsest_renderer.py'] = Path(raster_module.__file__)
            retain_tree(raster_directory, retained / 'raster')
            retained_raster = retained / 'raster/manifest.json'
            receipt.update(retained_raster_manifest_name='raster/manifest.json',
                           raster_manifest_relative_path=retained_raster.relative_to(output).as_posix())
            if dual:
                copies['mineru_ocr.log'] = output / 'mineru_ocr.log'
                retain_tree(ocr_directory, retained / 'ocr')
                for key in ('middle','model','origin'):
                    relative = Path('ocr') / ocr_paths[key].relative_to(ocr_directory)
                    receipt['retained_ocr_' + key + '_name'] = relative.as_posix()
                    receipt['ocr_' + key + '_relative_path'] = (retained / relative).relative_to(output).as_posix()
            else:
                for key in ('model','origin'):
                    receipt['retained_' + key + '_name'] = paths[key].name
            if digest(retained_raster) != receipt['raster_manifest_sha256']:
                raise ValueError("The retained raster manifest changed")
        for name, original_file in copies.items():
            target = retained / name
            if target.exists():
                raise ValueError("An evidence filename conflicts with raw parser output")
            shutil.copyfile(original_file, target)
            if digest(target) != digest(original_file):
                raise ValueError("Retained runtime/source evidence does not match")
        retained_artifacts = []
        for path in sorted(retained.rglob('*')):
            if path.is_symlink():
                raise ValueError("Parser output contains an unexpected symlink")
            if path.is_file():
                retained_artifacts.append({'path':path.relative_to(retained).as_posix(),
                                           'bytes':path.stat().st_size, 'sha256':digest(path)})
        artifacts = []
        for path in sorted(output.rglob("*")):
            if path.is_symlink():
                raise ValueError("Parser output contains an unexpected symlink")
            if path.is_file() and path.name != "status.json":
                artifacts.append({"path": path.relative_to(output).as_posix(),
                                  "bytes": path.stat().st_size, "sha256": digest(path)})
        receipt.update(status="complete", completed_pages=len(original), source_sha256_after=digest(source),
                       parser_origin_pages=origin,
                       middle_relative_path=paths["middle"].relative_to(output).as_posix(),
                       model_relative_path=paths["model"].relative_to(output).as_posix(),
                       origin_relative_path=paths["origin"].relative_to(output).as_posix(),
                       parser_page_sizes=[p["page_size"] for p in middle["pdf_info"]],
                       geometry_tolerance_points=1.0, origin_box_tolerance_points=0.03,
                       coordinate_system="Original PDF top-left points; recorded MinerU page-size rounding",
                       provenance_note="Middle JSON includes MinerU paragraph/table/title postprocessing; model JSON and all raw artifacts are retained separately. Page counts do not certify source fidelity.",
                       retained_middle_name=paths['middle'].name, retained_artifacts=retained_artifacts,
                       elapsed_seconds=time.monotonic() - started, artifacts=artifacts)
        if dual:
            receipt.update(phase="dual_transcriptions_complete",
                coordinate_system="Primary original PDF top-left points; secondary derived PDF top-left points require retained raster affine",
                provenance_note="Both complete raw transcriptions remain immutable. Original-PDF auto is primary; image200 OCR is separate source evidence. Selection is an audited application projection, not a source rewrite.")
        elif image:
            receipt.update(phase="image_transcription_complete",
                coordinate_system="Derived image-only PDF top-left points; map to original Data pages with the retained raster affine",
                provenance_note="One image200 OCR transcription is retained without native-text selection. Original source.pdf and all rendered pages/raw SDK artifacts remain immutable. Page and hash checks do not certify transcription fidelity.")
        write_json(retained / 'palimpsest_source_check.json', receipt)
        write_json(output / "parse_result.json", receipt)
        write_json(output / "status.json", receipt)
        print(json.dumps({k: receipt[k] for k in ("status", "document", "data_id", "page_count", "elapsed_seconds")}), flush=True)
    except BaseException as exc:
        try:
            receipt["source_sha256_after"] = digest(source)
        except OSError:
            receipt["source_sha256_after"] = None
        receipt.update(status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                       elapsed_seconds=time.monotonic() - started,
                       error_type=type(exc).__name__, error=str(exc))
        write_json(output / "status.json", receipt)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--document", required=True)
    parser.add_argument("--models-dir", type=Path, default=Path("/models"))
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--image-digest", required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
