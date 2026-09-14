"""Prepare the pinned T03 pipeline models in the dedicated /models volume.

Run with the script mounted read-only into palimpsest-mineru:3.4.5. Never
mount document inputs in this network-enabled preparation container. Parsing
uses this volume read-only with MINERU_MODEL_SOURCE=local and network disabled.
"""

import argparse
import fnmatch
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import tempfile


PACKAGE_VERSION = "3.4.5"
REPOSITORY = "opendatalab/PDF-Extract-Kit-1.0"
REVISION = "ed6b654c018d742e65a17671e379c5e6ecc87ec9"
ROOT = Path("/models")
MODEL_ROOT = ROOT / "pipeline"
CONFIG_PATH = ROOT / "mineru.json"
MANIFEST_PATH = ROOT / "manifest.json"
CONFIG = {"config_version": "1.3.2", "models-dir": {"pipeline": str(MODEL_ROOT)}}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def publish(path, value):
    """Publish complete metadata only; never replace a different finished profile."""
    body = encoded(value)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != body:
            raise ValueError("Existing model metadata differs from the pinned profile")
        return
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".palim-model-", dir=ROOT, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(body)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_path, path)
        directory = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def selected_paths():
    from mineru.utils.enum_class import ModelPath

    if importlib.metadata.version("mineru") != PACKAGE_VERSION or ModelPath.pipeline_root_hf != REPOSITORY:
        raise ValueError("Unexpected installed MinerU profile")
    # Exact list in the installed 3.4.5 cli/models_download.py:36-46.
    return [ModelPath.pp_doclayout_v2, ModelPath.unimernet_small, ModelPath.pytorch_paddle,
            ModelPath.slanet_plus, ModelPath.unet_structure, ModelPath.paddle_table_cls,
            ModelPath.pp_formulanet_plus_m]


def model_path(name, patterns):
    relative = PurePosixPath(name)
    if (relative.is_absolute() or ".." in relative.parts or "\\" in name or
            not any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)):
        raise ValueError("Unexpected model path")
    path = MODEL_ROOT.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(MODEL_ROOT.resolve()) or path.is_symlink():
        raise ValueError("Model path escapes its volume directory")
    return path


def verify(manifest, patterns):
    if (manifest["repository"] != REPOSITORY or manifest["revision"] != REVISION or
            manifest["mineru_version"] != PACKAGE_VERSION or manifest["allow_patterns"] != patterns):
        raise ValueError("Model manifest profile mismatch")
    if CONFIG_PATH.read_bytes() != encoded(CONFIG):
        raise ValueError("Model configuration mismatch")
    if digest(CONFIG_PATH) != manifest["config_sha256"]:
        raise ValueError("Model configuration digest mismatch")
    if not manifest["files"]:
        raise ValueError("Empty model manifest")
    names = set()
    for entry in manifest["files"]:
        path = model_path(entry["path"], patterns)
        if entry["path"] in names or path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
            raise ValueError("Model content mismatch")
        names.add(entry["path"])
    for required in selected_paths():
        if not any(name == required or name.startswith(required + "/") for name in names):
            raise ValueError("Required pipeline model is missing")


def prepare(verify_only=False):
    paths = selected_paths()
    patterns = [pattern for path in paths for pattern in (path, path + "/*")]
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        verify(manifest, patterns)
        return manifest
    if verify_only:
        raise ValueError("Models have not been prepared")

    # Import only for preparation; local verification makes no network requests.
    from huggingface_hub import HfApi, snapshot_download

    info = HfApi(token=False).model_info(REPOSITORY, revision=REVISION, files_metadata=True)
    if info.sha != REVISION:
        raise ValueError("Resolved model revision differs from requested commit")
    siblings = [file for file in info.siblings
                if any(fnmatch.fnmatchcase(file.rfilename, pattern) for pattern in patterns)]
    if not siblings:
        raise ValueError("No pipeline models matched the pinned revision")
    print(json.dumps({"status": "downloading", "repository": REPOSITORY, "revision": REVISION,
                      "files": len(siblings), "bytes": sum(file.size for file in siblings)}), flush=True)
    snapshot_download(repo_id=REPOSITORY, revision=REVISION, allow_patterns=patterns,
                      local_dir=MODEL_ROOT, token=False, max_workers=4)
    files = []
    for file in sorted(siblings, key=lambda item: item.rfilename):
        path = model_path(file.rfilename, patterns)
        checksum = digest(path)
        if path.stat().st_size != file.size:
            raise ValueError("Downloaded model size mismatch")
        if file.lfs:
            expected = file.lfs.sha256
            if not re.fullmatch(r"[a-f0-9]{64}", expected) or checksum != expected:
                raise ValueError("Downloaded LFS model digest mismatch")
        else:
            git_digest = hashlib.sha1(f"blob {file.size}\0".encode("ascii"))
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    git_digest.update(chunk)
            if git_digest.hexdigest() != file.blob_id:
                raise ValueError("Downloaded Git model blob mismatch")
        files.append({"path": file.rfilename, "bytes": file.size, "sha256": checksum,
                      "upstream_blob_id": file.blob_id})

    publish(CONFIG_PATH, CONFIG)
    manifest = {
        "schema_version": 1, "backend": "pipeline", "mineru_version": PACKAGE_VERSION,
        "repository": REPOSITORY, "revision": REVISION, "allow_patterns": patterns,
        "model_root": str(MODEL_ROOT), "config_path": str(CONFIG_PATH),
        "config_sha256": digest(CONFIG_PATH), "required_environment": {
            "MINERU_MODEL_SOURCE": "local", "MINERU_TOOLS_CONFIG_JSON": str(CONFIG_PATH),
        },
        "runtime": {"python": platform.python_version(), "packages": {
            name: importlib.metadata.version(name) for name in (
                "mineru", "torch", "torchvision", "transformers", "onnxruntime", "huggingface-hub")}},
        "files": files,
    }
    verify(manifest, patterns)
    publish(MANIFEST_PATH, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        manifest = prepare(args.verify_only)
        print(json.dumps({"status": "ready", "repository": REPOSITORY, "revision": REVISION,
                          "files": len(manifest["files"]), "bytes": sum(item["bytes"] for item in manifest["files"]),
                          "manifest_path": str(MANIFEST_PATH), "manifest_sha256": digest(MANIFEST_PATH),
                          "config_path": str(CONFIG_PATH), "config_sha256": manifest["config_sha256"],
                          "runtime": manifest["runtime"], "required_environment": manifest["required_environment"]}), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__,
                          "message": "Pinned pipeline model preparation or verification failed."}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
