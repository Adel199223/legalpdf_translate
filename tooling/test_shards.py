"""Collect once, assign whole test files, and run bounded isolated pytest workers.

No pytest dependency is imported in the planner/parent. CI workers independently
collect the same scope and prove identical plans; ``verify`` checks their actual
execution receipts and JUnit files before the required CI gate can pass.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


COUNTS = (1, 2, 4)
SCRIPT = Path(__file__).resolve()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_file(node_id):
    if not isinstance(node_id, str) or "::" not in node_id:
        raise ValueError("Expected a collected pytest node ID")
    name = node_id.split("::", 1)[0]
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts or ":" in name:
        raise ValueError("Test file must be repository-relative")
    return name


def make_plan(node_ids, shard_count=1, timings=None):
    """LPT balance measured file seconds, with per-case estimates for new files."""
    if type(shard_count) is not int or shard_count not in COUNTS:
        raise ValueError("Shard count must be 1, 2, or 4")
    if not node_ids or len(node_ids) != len(set(node_ids)):
        raise ValueError("Collection must be nonempty and contain no duplicate node IDs")
    files = {}
    for node in node_ids:
        files.setdefault(test_file(node), []).append(node)
    timings = {} if timings is None else timings
    if not isinstance(timings, dict):
        raise ValueError("Timings must map repository-relative files to positive seconds")
    for name, seconds in timings.items():
        test_file(name + "::placeholder")
        if type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("Timing weights must be finite positive numbers")
    rates = [timings[name] / len(nodes) for name, nodes in files.items() if name in timings]
    per_case = statistics.median(rates) if rates else 1.0
    weights = {name: float(timings.get(name, len(nodes) * per_case)) for name, nodes in files.items()}
    # Qt focus/window tests share a process-global GUI resource. Keep this
    # family together, including future files following the existing prefix.
    units = {}
    for name in files:
        basename = PurePosixPath(name).name
        affinity = "qt" if basename.startswith("test_qt_") or basename == "test_honorarios_docx.py" else name
        units.setdefault(affinity, []).append(name)
    assignments = [[] for _ in range(shard_count)]
    totals = [0.0] * shard_count
    for unit in sorted(units, key=lambda item: (-sum(weights[name] for name in units[item]), item)):
        index = min(range(shard_count), key=lambda i: (totals[i], i))
        assignments[index].extend(units[unit])
        totals[index] += sum(weights[name] for name in units[unit])
    shards = []
    for index, assigned in enumerate(assignments):
        chosen = set(assigned)
        nodes = [node for node in node_ids if test_file(node) in chosen]
        shards.append({"index": index, "files": [name for name in files if name in chosen],
                       "node_ids": nodes, "estimated_seconds": totals[index]})
    return {"version": 1, "collection_sha256": digest(node_ids), "node_ids": list(node_ids),
            "shard_count": shard_count, "file_weights": weights, "shards": shards}


def junit_summary(path):
    data = Path(path).read_bytes()
    root = ET.fromstring(data)
    cases = list(root.iter("testcase"))
    return {"sha256": hashlib.sha256(data).hexdigest(), "tests": len(cases),
            "failures": sum(len(case.findall("failure")) for case in cases),
            "errors": sum(len(case.findall("error")) for case in cases),
            "skipped": sum(len(case.findall("skipped")) for case in cases)}


def stop_owned(processes):
    """Stop only subprocess trees created by this invocation, then reap them."""
    for process in processes:
        if process.poll() is not None:
            continue
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def launch_requests(requests, repo):
    processes = []
    starts = []
    reported = set()
    with ExitStack() as stack:
        try:
            for request, folder in requests:
                folder.mkdir()
                execution_root = Path(request["execution_root"])
                execution_root.mkdir()
                request_path = folder / "request.json"
                write_json(request_path, request)
                env = os.environ.copy()
                for key, child in [("APPDATA", "appdata"), ("LOCALAPPDATA", "localappdata"),
                                   ("TEMP", "temp"), ("TMP", "temp")]:
                    path = execution_root / child
                    path.mkdir(exist_ok=True)
                    env[key] = str(path)
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                fonts = Path(env.get("WINDIR", "C:/Windows")) / "Fonts"
                if os.name == "nt" and env.get("QT_QPA_PLATFORM") == "offscreen" and fonts.is_dir():
                    env.setdefault("QT_QPA_FONTDIR", str(fonts))
                kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
                process = subprocess.Popen([sys.executable, "-B", str(SCRIPT), "_pytest", str(request_path)],
                    cwd=repo, env=env, stdout=stack.enter_context((folder / "stdout.log").open("w", encoding="utf-8")),
                    stderr=stack.enter_context((folder / "stderr.log").open("w", encoding="utf-8")), **kwargs)
                processes.append(process)
                starts.append(time.monotonic())
                print(f"[test-shards] Started {folder.name}; log: {folder / 'stdout.log'}", flush=True)
            while any(process.poll() is None for process in processes):
                for index, process in enumerate(processes):
                    if process.poll() is not None and index not in reported:
                        print(f"[test-shards] {requests[index][1].name} exited {process.returncode} "
                              f"after {time.monotonic() - starts[index]:.2f}s", flush=True)
                        reported.add(index)
                time.sleep(0.1)
            for index, process in enumerate(processes):
                if index not in reported:
                    print(f"[test-shards] {requests[index][1].name} exited {process.returncode} "
                          f"after {time.monotonic() - starts[index]:.2f}s", flush=True)
            return [process.returncode for process in processes]
        except BaseException:
            stop_owned(processes)
            raise


def pytest_child(request_path):
    """Internal entry point: normal pytest/conftest remain fully active."""
    import pytest

    request = read_json(request_path)
    folder = Path(request_path).parent
    execution_root = Path(request["execution_root"])
    expected = request.get("plan")
    owned = expected["shards"][request["index"]]["node_ids"] if expected else None
    collected = []
    phases = []

    class Evidence:
        @pytest.hookimpl(wrapper=True, tryfirst=True)
        def pytest_collection_modifyitems(self, config, items):
            yield
            actual = [item.nodeid for item in items]
            collected[:] = actual
            write_json(folder / "collection.json", {"node_ids": actual, "sha256": digest(actual)})
            if expected is not None:
                if actual != expected["node_ids"]:
                    raise pytest.UsageError("Collected scope changed since shard planning")
                keep = set(owned)
                excluded = [item for item in items if item.nodeid not in keep]
                items[:] = [item for item in items if item.nodeid in keep]
                config.hook.pytest_deselected(items=excluded)

        def pytest_collection_finish(self, session):
            if expected is not None and [item.nodeid for item in session.items] != owned:
                raise pytest.UsageError("Final worker collection differs from its exact assignment")

        def pytest_runtest_logreport(self, report):
            phases.append({"node_id": report.nodeid, "phase": report.when,
                           "outcome": report.outcome, "seconds": report.duration})

    args = ["--rootdir", request["repo"], *request["pytest_args"], "--basetemp", str(execution_root / "pytest"),
            "-o", "cache_dir=" + str(execution_root / "cache")]
    if expected is None:
        args += ["--collect-only", "-q", "-p", "no:cacheprovider"]
    else:
        args += ["-q", "--durations=25", "--junitxml=" + str(folder / "junit.xml")]
    started = time.monotonic()
    code = int(pytest.main(args, plugins=[Evidence()]))
    executed = [phase["node_id"] for phase in phases if phase["phase"] == "call" or
                (phase["phase"] == "setup" and phase["outcome"] != "passed")]
    # Exit 0 without executing the planned cases is not a successful worker.
    if expected is not None and (executed != owned or not owned) and code == 0:
        code = 1
    write_json(folder / "execution.json", {"exit_code": code, "seconds": time.monotonic() - started,
               "collection_sha256": digest(collected), "executed_node_ids": executed, "phases": phases})
    return code


def run_suite(repo, output, pytest_args, *, workers=1, shard_count=None, shard_index=None, timings=None):
    if workers not in COUNTS:
        raise ValueError("Workers must be 1, 2, or 4")
    count = workers if shard_count is None else shard_count
    if count not in COUNTS or ((shard_index is None) != (shard_count is None)):
        raise ValueError("Use --shard-count and --shard-index together")
    if shard_index is not None and (workers != 1 or not 0 <= shard_index < count):
        raise ValueError("A CI shard requires workers=1 and an index within its shard count")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    repo = Path(repo).resolve()
    base = {"repo": str(repo), "pytest_args": list(pytest_args or ["tests"])}
    status = {"version": 1, "exit_code": 1, "status": "collecting", "workers": []}
    try:
        # Short, fresh roots avoid adding report-directory depth to every
        # fixture filesystem operation. Retain these roots, especially on
        # failures; only private request.json records their absolute paths.
        execution_parent = Path(tempfile.mkdtemp(prefix="lpt-"))
        code = launch_requests([(base | {"execution_root": str(execution_parent / "c")}, output / "collection")], repo)[0]
        if code:
            status.update(status="collection_failed", exit_code=code)
            return code
        nodes = read_json(output / "collection" / "collection.json")["node_ids"]
        plan = make_plan(nodes, count, timings)
        write_json(output / "plan.json", plan)
        print(f"[test-shards] Collected {len(nodes)} cases in {len(plan['file_weights'])} files; "
              f"collection SHA256 {plan['collection_sha256']}", flush=True)
        for part in plan["shards"]:
            print(f"[test-shards] Shard {part['index']}: {len(part['node_ids'])} cases, "
                  f"{len(part['files'])} files, estimated weight {part['estimated_seconds']:.2f}", flush=True)
        status.update(plan_sha256=digest(plan), collection_sha256=plan["collection_sha256"],
                      shard_count=count, status="running")
        indexes = [shard_index] if shard_index is not None else list(range(count))
        if any(not plan["shards"][index]["node_ids"] for index in indexes):
            raise ValueError("An empty shard cannot pass; use fewer shards for this scope")
        requests = [(base | {"plan": plan, "index": index, "execution_root": str(execution_parent / f"w{index}")},
                     output / f"worker-{index}") for index in indexes]
        codes = launch_requests(requests, repo)
        for index, code in zip(indexes, codes):
            folder = output / f"worker-{index}"
            execution = read_json(folder / "execution.json") if (folder / "execution.json").exists() else None
            junit = junit_summary(folder / "junit.xml") if (folder / "junit.xml").exists() else None
            good = (code == 0 and execution is not None and execution["exit_code"] == 0 and
                    execution["executed_node_ids"] == plan["shards"][index]["node_ids"] and
                    execution["collection_sha256"] == plan["collection_sha256"] and junit is not None and
                    junit["tests"] == len(plan["shards"][index]["node_ids"]) and not junit["errors"] and not junit["failures"])
            status["workers"].append({"index": index, "exit_code": code if code else (0 if good else 1),
                                      "directory": folder.name, "junit": junit})
        result = next((worker["exit_code"] for worker in status["workers"] if worker["exit_code"]), 0)
        status.update(status="passed" if result == 0 else "failed", exit_code=result)
        return result
    except KeyboardInterrupt:
        status.update(status="interrupted", exit_code=130)
        return 130
    except Exception as error:
        status.update(status="infrastructure_failed", exit_code=1, error_class=type(error).__name__)
        print(f"[test-shards] Infrastructure failure: {type(error).__name__}", file=sys.stderr, flush=True)
        return 1
    finally:
        write_json(output / "result.json", status)


def verify_results(paths):
    if not paths:
        raise ValueError("No worker results supplied")
    plan = None
    indexes = set()
    executed = []
    for path in paths:
        path = Path(path)
        result = read_json(path)
        candidate = read_json(path.parent / "plan.json")
        # Recompute the plan to detect inconsistent or omitted assignments.
        canonical = make_plan(candidate["node_ids"], candidate["shard_count"], candidate["file_weights"])
        if canonical != candidate or result.get("plan_sha256") != digest(candidate):
            raise ValueError("Invalid partition plan")
        if plan is None:
            plan = candidate
        if candidate != plan or result.get("collection_sha256") != plan["collection_sha256"]:
            raise ValueError("Workers did not collect and plan the same tests")
        if result.get("exit_code") != 0 or result.get("status") != "passed":
            raise ValueError("A worker invocation did not pass")
        for worker in result["workers"]:
            index = worker["index"]
            if type(index) is not int or index not in range(plan["shard_count"]) or index in indexes:
                raise ValueError("Duplicate or invalid shard index")
            if worker["directory"] != f"worker-{index}" or worker["exit_code"] != 0:
                raise ValueError("Invalid worker result")
            folder = path.parent / worker["directory"]
            execution = read_json(folder / "execution.json")
            junit = junit_summary(folder / "junit.xml")
            nodes = plan["shards"][index]["node_ids"]
            if (not nodes or execution["exit_code"] != 0 or execution["collection_sha256"] != plan["collection_sha256"] or
                    execution["executed_node_ids"] != nodes or junit != worker["junit"] or
                    junit["tests"] != len(nodes) or junit["failures"] or junit["errors"]):
                raise ValueError("Worker execution or JUnit does not prove its assigned tests")
            indexes.add(index)
            executed.extend(nodes)
    if indexes != set(range(plan["shard_count"])) or len(executed) != len(set(executed)) or set(executed) != set(plan["node_ids"]):
        raise ValueError("Worker coverage is not exhaustive and nonoverlapping")
    return {"status": "passed", "collection_sha256": plan["collection_sha256"], "plan_sha256": digest(plan),
            "shards": len(indexes), "tests": len(executed)}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_pytest":
        return pytest_child(Path(argv[1]))
    pytest_args = []
    if "--" in argv:
        split = argv.index("--")
        argv, pytest_args = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--repo", type=Path, default=Path.cwd())
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--workers", type=int, choices=COUNTS, default=1)
    run.add_argument("--shard-count", type=int, choices=COUNTS)
    run.add_argument("--shard-index", type=int)
    run.add_argument("--timings", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--output", required=True, type=Path)
    verify.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args(argv)
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupted)
    try:
        if args.command == "run":
            return run_suite(args.repo, args.output, pytest_args, workers=args.workers,
                shard_count=args.shard_count, shard_index=args.shard_index,
                timings=read_json(args.timings) if args.timings else None)
        result = verify_results(args.results)
        args.output.mkdir(parents=True, exist_ok=False)
        write_json(args.output / "verification.json", result)
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError) as error:
        print(f"Test shard validation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
