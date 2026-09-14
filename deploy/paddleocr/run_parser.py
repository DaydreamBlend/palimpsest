"""Run the pinned, local PaddleOCR-VL pipeline and retain page-level evidence.

This worker writes parser artifacts only. It neither imports Data nor commits I.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import time


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def asset_path(directory: Path, relative: str) -> Path:
    """Validate SDK image paths before its Markdown writer uses them."""
    path = PurePosixPath(relative)
    if (
        not relative or "\\" in relative or ":" in relative
        or path.is_absolute() or ".." in path.parts
    ):
        raise ValueError(f"Unsafe SDK image path: {relative!r}")
    resolved = directory.joinpath(*path.parts).resolve()
    if not resolved.is_relative_to(directory.resolve()):
        raise ValueError("SDK image path escapes the page output")
    return resolved


def page_geometry(page, page_index: int) -> dict:
    rotation = page.get_rotation()
    if rotation != 0:
        raise ValueError(f"Page {page_index + 1}: unsupported PDF rotation {rotation}")
    cropbox = list(page.get_cropbox())
    bounds = list(page.get_bbox())
    size = list(page.get_size())
    if not all(math.isfinite(value) for value in cropbox + bounds + size):
        raise ValueError(f"Page {page_index + 1}: non-finite page geometry")
    if any(not math.isclose(a, b, abs_tol=0.001) for a, b in zip(cropbox, bounds)):
        raise ValueError(f"Page {page_index + 1}: CropBox outside MediaBox is unsupported")
    expected_size = [cropbox[2] - cropbox[0], cropbox[3] - cropbox[1]]
    if min(size) <= 0 or any(
        not math.isclose(a, b, abs_tol=0.001) for a, b in zip(size, expected_size)
    ):
        raise ValueError(f"Page {page_index + 1}: inconsistent crop dimensions")
    return {
        "page_index": page_index,
        "pdf_size": size,
        "rotation": rotation,
        "cropbox": cropbox,
        "source_box": "crop",
    }


def save_result(result, raw: dict, page_dir: Path, output: Path) -> list[dict]:
    blocks = result["parsing_res_list"]
    raw_blocks = raw["parsing_res_list"]
    if len(blocks) != len(raw_blocks):
        raise ValueError("SDK block objects and raw JSON have different lengths")
    for block in blocks:
        if block.image is not None:
            asset_path(page_dir, block.image["path"])
    for image in result.get("imgs_in_doc", []):
        asset_path(page_dir, image["path"])

    # Explicit filenames avoid the SDK's random name for ndarray inputs.
    result.save_to_json(str(page_dir / "sdk_result.json"))
    result.save_to_markdown(
        str(page_dir / "page.md"), pretty=False, show_formula_number=True
    )
    # SDK box annotations lazily fetch a remote font. Retained source-page PNGs,
    # raw region coordinates and actual crop files provide offline visual QA.
    assets = []
    for index, (block, raw_block) in enumerate(zip(blocks, raw_blocks)):
        if raw_block["block_id"] != index or list(block.bbox) != raw_block["block_bbox"]:
            raise ValueError("SDK image cannot be aligned with its raw block")
        if block.image is None:
            continue
        path = asset_path(page_dir, block.image["path"])
        if not path.is_file():
            raise ValueError(f"SDK did not save image asset for block {index}")
        assets.append({
            "block_id": index,
            "path": path.relative_to(output).as_posix(),
            "sha256": sha256(path),
            "bbox": raw_block["block_bbox"],
        })
    return assets


def create_pipeline(models_dir: Path, output: Path):
    import paddlex
    import torch
    import yaml
    from paddleocr import PaddleOCRVL

    if not torch.cuda.is_available():
        raise RuntimeError("This pinned GPU worker requires a visible CUDA device")
    config_path = Path(paddlex.__file__).parent / "configs/pipelines/PaddleOCR-VL-1.6.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config.update(batch_size=1, use_queues=False, markdown_ignore_labels=[], merge_layout_blocks=False)
    for name, folder, dtype in (
        ("LayoutDetection", "layout", "float32"),
        ("VLRecognition", "vl", "bfloat16"),
    ):
        module = config["SubModules"][name]
        module.update(
            model_dir=str(models_dir / folder), batch_size=1,
            engine="transformers",
            engine_config={"dtype": dtype, "trust_remote_code": False},
        )
    write_json(output / "requested_pipeline.json", config)
    pipeline = PaddleOCRVL(
        pipeline_version="v1.6", paddlex_config=config,
        engine="transformers", device="gpu:0",
        use_doc_orientation_classify=False, use_doc_unwarping=False,
        use_layout_detection=True, use_chart_recognition=False,
        use_seal_recognition=False, use_ocr_for_image_block=False,
        format_block_content=False, merge_layout_blocks=False,
        markdown_ignore_labels=[], use_queues=False,
    )
    pipeline.export_paddlex_config_to_yaml(str(output / "resolved_pipeline.yaml"))
    return pipeline


def run(args) -> None:
    # The enclosing Docker worker is also expected to have networking disabled.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    import numpy as np
    import pypdfium2 as pdfium
    import torch

    source = args.input.resolve(strict=True)
    output = args.output.resolve()
    models = args.models_dir.resolve(strict=True)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; retain failed attempts separately")
    output.mkdir(parents=True, exist_ok=True)
    if source.is_relative_to(output):
        raise ValueError("Input PDF must be outside the output directory")
    for folder in ("layout", "vl"):
        for filename in ("model.safetensors", "config.json", "inference.yml"):
            if not (models / folder / filename).is_file():
                raise ValueError(f"Missing pinned local model file: {folder}/{filename}")
    manifest_path = models / 'manifest.json'
    model_manifest_hash = sha256(manifest_path)
    runner_hash = sha256(Path(__file__))
    profile = None
    if args.profile is not None:
        profile = json.loads(args.profile.read_text(encoding='utf-8'))
        parser_profile = profile['parser']
        if (parser_profile['models_manifest_sha256'] != model_manifest_hash
                or any(parser_profile.get(key) != value for key, value in {
                    'provider': 'paddleocr-vl', 'version': '3.7.0', 'backend': 'transformers',
                    'pipeline_version': 'v1.6', 'adapter_version': 'paddleocr-raw-v1',
                }.items())
                or profile['policy']['implementation_sha256'].get('deploy/paddleocr/run_parser.py') != runner_hash):
            raise ValueError('Compilation parser/model/implementation profile mismatch')
    for model in json.loads(manifest_path.read_text(encoding='utf-8')):
        for artifact in model['files']:
            path = asset_path(models / model['name'], artifact['path'])
            if sha256(path) != artifact['sha256']:
                raise ValueError('Pinned model artifact hash mismatch')
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    torch.cuda.manual_seed_all(42)
    data_id = sha256(source)
    start = time.monotonic()
    document = pdfium.PdfDocument(str(source))
    pipeline = None
    pages = []
    receipt = {
        "schema_version": "paddleocr-raw-v1", "data_id": data_id,
        "document": args.document, "page_count": len(document),
        "render_scale": 2, "seed": 42,
        "models_manifest_sha256": model_manifest_hash,
        "runner_sha256": runner_hash,
        "coordinate_convention": "cropbox is PDF left,bottom,right,top; block bbox is rendered image left,top,right,bottom",
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("paddleocr", "paddlex", "transformers", "torch", "pypdfium2")
        },
    }
    try:
        if len(document) == 0:
            raise ValueError("PDF has no pages")
        geometries = []
        for index in range(len(document)):
            page = document[index]
            try:
                geometries.append(page_geometry(page, index))
            finally:
                page.close()
        write_json(output / "status.json", {**receipt, "status": "running", "completed_pages": 0})
        pipeline = create_pipeline(models, output)
        (output / "pages").mkdir()
        for index, geometry in enumerate(geometries):
            page_start = time.monotonic()
            page_dir = output / f"sdk/page_{index + 1:04d}"
            page_dir.mkdir(parents=True)
            render_path = output / f"pages/page_{index + 1:04d}.png"
            page = document[index]
            try:
                bitmap = page.render(scale=2, rotation=0)
                try:
                    pil_image = bitmap.to_pil().convert("RGB")
                    pil_image.save(render_path)
                    render_size = list(pil_image.size)
                    # PaddleX interprets ndarray input as OpenCV BGR, not PIL RGB.
                    image_bgr = np.asarray(pil_image)[:, :, ::-1].copy()
                finally:
                    bitmap.close()
            finally:
                page.close()
            results = iter(pipeline.predict(image_bgr, max_new_tokens=4096, temperature=0))
            result = next(results, None)
            if result is None or next(results, None) is not None:
                raise ValueError("Expected exactly one SDK result for one rendered page")
            raw = result.json["res"]
            if raw["model_settings"].get("merge_layout_blocks") is not False:
                raise ValueError("Text merging would lose per-region source grounding")
            if [raw["width"], raw["height"]] != render_size:
                raise ValueError("SDK output dimensions differ from the retained page render")
            page_receipt = {
                **geometry, "render_size": render_size,
                "render_path": render_path.relative_to(output).as_posix(),
                "render_sha256": sha256(render_path), "result": raw,
                "image_assets": save_result(result, raw, page_dir, output),
                "elapsed_seconds": time.monotonic() - page_start,
            }
            write_json(page_dir / "page_receipt.json", page_receipt)
            pages.append(page_receipt)
            write_json(output / "status.json", {
                **receipt, "status": "running", "completed_pages": len(pages),
            })
            print(json.dumps({"page_completed": index + 1, "page_count": len(document)}, ensure_ascii=False), flush=True)
        if sha256(source) != data_id:
            raise ValueError("Input PDF changed during parsing")
        if sha256(Path(__file__)) != runner_hash:
            raise ValueError("Parser implementation changed during parsing")
        write_json(output / "paddle_raw.json", {**receipt, "pages": pages})
        if profile is not None:
            encoded = json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
            write_json(output / 'parse_result.json', {
                'data_id': data_id, 'page_count': len(pages), 'middle_relative_path': 'paddle_raw.json',
                'compilation_profile_sha256': hashlib.sha256(encoded).hexdigest(),
                'models_manifest_sha256': model_manifest_hash,
            })
        write_json(output / "status.json", {
            **receipt, "status": "complete", "completed_pages": len(pages),
            "elapsed_seconds": time.monotonic() - start,
            "raw_sha256": sha256(output / "paddle_raw.json"),
        })
    except BaseException as exc:
        write_json(output / "status.json", {
            **receipt, "status": "failed", "completed_pages": len(pages),
            "error_type": type(exc).__name__, "error": str(exc),
        })
        raise
    finally:
        if pipeline is not None:
            pipeline.close()
        document.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--document", required=True)
    parser.add_argument("--models-dir", default=Path("/models"), type=Path)
    parser.add_argument("--profile", type=Path, help="Optional Palimpsest compilation profile")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
