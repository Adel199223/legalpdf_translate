"""Verify the newest attempt of every shard from one workflow run's artifacts.

The caller downloads artifacts scoped to the current GitHub workflow run. This
module performs no network operations and requires only the standard library.
Older attempts are preserved and never substituted for a failed latest attempt.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

if __package__:
    from . import test_shards
else:
    import test_shards


ARTIFACT = re.compile(r"pytest-shard-([0-3])-attempt-([0-9]+)\Z")
SHARD_COUNT = 4


def select_artifacts(root):
    """Select by integer attempt, rejecting ambiguous or malformed names."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Artifact root is not a directory")
    candidates = {}
    latest = {}
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if not entry.name.startswith("pytest-shard-"):
            continue
        match = ARTIFACT.fullmatch(entry.name)
        if match is None or int(match[2]) < 1 or not entry.is_dir() or entry.is_symlink():
            raise ValueError(f"Malformed shard artifact: {entry.name}")
        index, attempt = int(match[1]), int(match[2])
        key = (index, attempt)
        if key in candidates:
            raise ValueError(f"Duplicate artifact for shard {index}, attempt {attempt}")
        candidates[key] = entry
        if index not in latest or attempt > latest[index][0]:
            latest[index] = (attempt, entry)
    if set(latest) != set(range(SHARD_COUNT)):
        raise ValueError("Artifacts are missing one or more of the four shards")
    return [{"index": index, "attempt": latest[index][0], "artifact": latest[index][1].name}
            for index in range(SHARD_COUNT)]


def verify_artifacts(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    # An existing receipt or prior artifact must never be overwritten.
    output.mkdir(parents=True, exist_ok=False)
    try:
        selection = select_artifacts(root)
        test_shards.write_json(output / "selection.json", {"shards": selection})
        results = []
        for chosen in selection:
            folder = root / chosen["artifact"]
            result_path, plan_path = folder / "result.json", folder / "plan.json"
            if not result_path.is_file() or not plan_path.is_file():
                raise ValueError(f"Latest artifact is missing a receipt: {chosen['artifact']}")
            plan, result = test_shards.read_json(plan_path), test_shards.read_json(result_path)
            if type(plan.get("shard_count")) is not int or plan["shard_count"] != SHARD_COUNT:
                raise ValueError("Selected artifact does not describe a four-shard plan")
            workers = result.get("workers", [])
            if len(workers) != 1 or workers[0].get("index") != chosen["index"]:
                raise ValueError("Artifact name does not match its sole worker index")
            results.append(result_path)
        verified = test_shards.verify_results(results)
        if verified["shards"] != SHARD_COUNT:
            raise ValueError("Verification did not cover all four shards")
        receipt = {**verified, "selected_artifacts": selection}
        test_shards.write_json(output / "verification.json", receipt)
        return receipt
    except Exception as error:
        test_shards.write_json(output / "verification.json", {
            "status": "failed", "error_class": type(error).__name__, "error": str(error)})
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_artifacts(args.artifacts, args.output)
    except Exception as error:
        print(f"CI shard evidence rejected: {error}", file=sys.stderr)
        return 1
    attempts = ", ".join(f"{item['index']}:{item['attempt']}" for item in result["selected_artifacts"])
    print(f"Verified {result['tests']} tests across four shards; selected shard:attempt {attempts}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
