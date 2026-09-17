"""Run pending structured model requests in one batch directory at C4."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def pending(directory, retry_failures=False, names=None):
    result = []
    if names is not None and any(not isinstance(name, str) or Path(name).name != name for name in names):
        raise ValueError("invalid_job_directory")
    requests = ((directory / name / "request.json" for name in names)
                if names is not None else directory.glob("*/request.json"))
    for request in sorted(requests):
        value = json.loads(request.read_text(encoding="utf-8"))
        output = request.parent / value["output_file"]
        if not output.exists() and (retry_failures or not output.with_suffix(".failure.json").exists()):
            result.append(request)
    return result


def archive_failure(request):
    value = json.loads(request.read_text(encoding="utf-8"))
    output = request.parent / value["output_file"]
    failure = output.with_suffix(".failure.json")
    if not failure.exists():
        return
    attempt = 1
    while True:
        archived = output.with_name(f"{output.stem}.attempt{attempt}.failure{output.suffix}")
        if not archived.exists():
            failure.rename(archived)
            return
        attempt += 1


def run(request, provider, timeout):
    command = [sys.executable, str(ROOT / "tools/run_knowledge_model.py"), str(request),
               "--provider", provider, "--timeout-seconds", str(timeout)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return {"batch": request.parent.name, "returncode": completed.returncode,
            "output": completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--provider", choices=("local-glm", "codex-terra"), default="local-glm")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    parser.add_argument("--retry-failures", action="store_true",
                        help="retry preserved failed requests without overwriting their receipts")
    parser.add_argument("--job-manifest", type=Path,
                        help="only run current job directories from a jobs.json manifest")
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 4 or args.timeout_seconds <= 0:
        parser.error("concurrency must be 1..4 and timeout must be positive")
    names = None
    if args.job_manifest:
        jobs = json.loads(args.job_manifest.resolve(strict=True).read_text(encoding="utf-8"))["jobs"]
        names = [job.get("directory", f"g{job['ordinal']:04d}") for job in jobs]
    requests = pending(args.directory.resolve(strict=True), args.retry_failures, names)
    if args.retry_failures:
        for request in requests:
            archive_failure(request)
    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run, request, args.provider, args.timeout_seconds) for request in requests]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    failed = [result for result in results if result["returncode"]]
    print(json.dumps({"requested": len(requests), "completed": len(results) - len(failed),
                      "failed": len(failed), "concurrency": args.concurrency}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
