"""Prepare or merge resumable strict-JSON I2K batch calls."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from palimpsest import batched_i2k
from palimpsest.local_glm_provider import PROFILE as MODEL


def _read(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    return value["result"] if value.get("command_status") == "succeeded" else value


def _assets(directory):
    root = directory.resolve(strict=True)
    values = json.loads((root / "attachments.json").read_text(encoding="utf-8"))
    result = {}
    for value in values:
        path = (root / value["relative_path"]).resolve(strict=True)
        raw = path.read_bytes()
        if (not path.is_relative_to(root) or len(raw) != value["byte_size"]
                or sha256(raw).hexdigest() != value["sha256"] or value["sha256"] in result):
            raise ValueError("Attachment manifest mismatch")
        result[value["sha256"]] = (value, path)
    return result


def prepare(context_path, attachments, directory, phase):
    context = _read(context_path)
    plan = batched_i2k.requests(context, phase)
    assets = _assets(attachments)
    directory.mkdir(parents=True, exist_ok=True)
    summary = []
    for batch in plan["batches"]:
        batch_dir = directory / batch["batch_id"]
        batch_dir.mkdir(exist_ok=True)
        request = {key: value for key, value in batch["request"].items()
                   if key != "image_sha256s"}
        request["images"] = [{"path": os.path.relpath(assets[sha][1], batch_dir), "sha256": sha}
                             for sha in batch["image_sha256s"]]
        path = batch_dir / "request.json"
        encoded = json.dumps(request, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") != encoded:
            raise ValueError("Existing batch request changed")
        if not path.exists():
            path.write_text(encoded, encoding="utf-8")
        summary.append({"batch_id": batch["batch_id"], "information": len(batch["information_ids"]),
                        "targets": len(batch["target_ids"]), "images": len(batch["image_sha256s"]),
                        "prompt_characters": len(request["prompt"]),
                        "response_exists": (batch_dir / "response.json").is_file()})
    manifest = {key: value for key, value in plan.items() if key != "batches"}
    manifest["batches"] = [{key: batch[key] for key in
        ("batch_id", "information_ids", "target_ids", "image_sha256s")} for batch in plan["batches"]]
    manifest_path = directory / "manifest.json"
    encoded = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != encoded:
        raise ValueError("Existing batch manifest changed")
    if not manifest_path.exists():
        manifest_path.write_text(encoded, encoding="utf-8")
    return {"phase": phase, "batches": summary, "plan_sha256": plan["plan_sha256"]}


def merge(context_path, directory, output, phase):
    context = _read(context_path)
    plan = batched_i2k.requests(context, phase)
    exchanges = []
    for batch in plan["batches"]:
        path = directory / batch["batch_id"] / "response.json"
        exchanges.append(json.loads(path.read_text(encoding="utf-8")))
    result = batched_i2k.aggregate(context, phase, exchanges, MODEL)
    encoded = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != encoded:
        raise ValueError("Existing aggregate exchange changed")
    if not output.exists():
        output.write_text(encoded, encoding="utf-8")
    return {"phase": phase, "batches": len(exchanges),
            "nodes_or_decisions": len(result["response"].get(
                "nodes", result["response"].get("decisions", []))),
            "complete": result["response"]["complete"], "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "merge"))
    parser.add_argument("phase", choices=("generator", "validator"))
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--attachments", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.attachments is None or args.output is not None:
            parser.error("prepare requires --attachments and no --output")
        result = prepare(args.context, args.attachments, args.directory, args.phase)
    else:
        if args.output is None or args.attachments is not None:
            parser.error("merge requires --output and no --attachments")
        result = merge(args.context, args.directory, args.output, args.phase)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
