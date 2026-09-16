"""Offline synthetic acceptance tests under explicit trusted-runtime assumptions.

Not a security sandbox for hostile Python/native code, not a paid caller, and
not a replacement for any historical private guard. No module-name exemptions.
The interpreter, its startup and installed dependencies are trusted. The audit
policy catches cooperative Python-visible side effects before pytest imports.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time


REPOSITORY = Path(__file__).resolve().parents[1]
CANONICAL_PYTHON = Path("C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe")
OUTPUT_PARENT = Path("C:/Users/FA507/.codex/legalpdf_translate_private_benchmarks")
TESTS = (
    "tests/test_isolated_acceptance_runner.py",
    "tests/test_budget_reservations.py",
    "tests/test_ordinary_accounting_policy.py",
    "tests/test_acceptance_budget_adapter.py",
    "tests/test_acceptance_provenance.py",
    "tests/test_transport_client_isolation.py",
    "tests/test_activation_policy.py",
    "tests/test_acceptance_campaign_integration.py",
    "tests/test_structured_acceptance_run.py",
    "tests/test_acceptance_runtime_boundary.py",
    "tests/test_acceptance_openai_sdk.py",
    "tests/test_acceptance_recovery.py",
    "tests/test_acceptance_legacy_recovery.py",
    "tests/test_acceptance_historical_instructions.py",
    "tests/test_acceptance_review.py",
    "tests/test_acceptance_assembly.py",
    "tests/test_reviewed_formatting.py",
    "tests/test_reviewed_folios.py",
    "tests/test_reviewed_folio_cells.py",
    "tests/test_reviewed_regions.py",
    "tests/test_reviewed_column_gutters.py",
    "tests/test_docx_numeric_slash_runs.py",
    "tests/test_docx_clock_runs.py",
    "tests/test_docx_clock_contexts.py",
    "tests/test_docx_clock_rebuild.py",
    "tests/test_docx_writer_rtl.py",
    "tests/test_formatting_support.py",
    "tests/test_reviewed_cell_boundaries.py",
    "tests/test_reviewed_inline_cells.py",
    "tests/test_reviewed_source_gaps.py",
    "tests/test_acceptance_ignored_sidecars.py",
    "tests/test_run_docx_formatting.py",
    "tests/test_operator_run_docx_formatting.py",
    "tests/test_formatting_review_cli.py",
    "tests/test_reviewed_rebuild_workflow.py",
    "tests/test_run_workspace_lock.py",
    "tests/test_layout_review_versions.py",
    "tests/test_structured_arabic_signature_abbreviation.py",
    "tests/test_reviewed_region_writer.py",
    "tests/test_reviewed_formatting_v2.py",
    "tests/test_reviewed_formatting_writer.py",
    "tests/test_reviewed_formatting_writer_arabic.py",
    "tests/test_acceptance_formatting.py",
    "tests/test_acceptance_model_selection.py",
    "tests/test_terra_client_selection.py",
    "tests/test_structured_acceptance_prepare.py",
    "tests/test_acceptance_successor.py",
)
CALLER_TESTS = ("tests/test_isolated_acceptance_runner.py", "tests/test_structured_acceptance_run.py")
BOUNDARY_TESTS = ("tests/test_acceptance_runtime_boundary.py",)
SDK_TESTS = ("tests/test_acceptance_openai_sdk.py",)
RECOVERY_TESTS = ("tests/test_acceptance_historical_instructions.py",
                  "tests/test_acceptance_recovery.py", "tests/test_acceptance_review.py",
                  "tests/test_acceptance_legacy_recovery.py")
LEGACY_RECOVERY_TESTS = ("tests/test_acceptance_legacy_recovery.py",)
ASSEMBLY_TESTS = ("tests/test_acceptance_assembly.py",)
FORMATTING_TESTS = ("tests/test_docx_numeric_slash_runs.py", "tests/test_docx_clock_runs.py", "tests/test_docx_clock_contexts.py", "tests/test_docx_clock_rebuild.py", "tests/test_docx_writer_rtl.py", "tests/test_formatting_support.py", "tests/test_reviewed_column_gutters.py", "tests/test_reviewed_cell_boundaries.py", "tests/test_reviewed_inline_cells.py", "tests/test_reviewed_source_gaps.py", "tests/test_reviewed_folio_cells.py", "tests/test_reviewed_regions.py", "tests/test_reviewed_folios.py", "tests/test_reviewed_formatting_v2.py", "tests/test_reviewed_region_writer.py", "tests/test_reviewed_formatting.py", "tests/test_reviewed_formatting_writer.py",
                    "tests/test_reviewed_formatting_writer_arabic.py",
                    "tests/test_acceptance_ignored_sidecars.py", "tests/test_run_docx_formatting.py")
FORMATTED_ASSEMBLY_TESTS = ("tests/test_acceptance_formatting.py",)
ORDINARY_FORMATTING_TESTS = ("tests/test_reviewed_rebuild_workflow.py",
    "tests/test_run_workspace_lock.py", "tests/test_layout_review_versions.py",
    "tests/test_run_docx_formatting.py", "tests/test_operator_run_docx_formatting.py",
    "tests/test_formatting_review_cli.py")
ORDINARY_SOURCE_TESTS = (
    "tests/test_ordinary_reviewed_source.py",
    "tests/test_ordinary_source_review_service.py",
    "tests/test_browser_source_review.py",
)
REVIEW_SERVICE_TESTS = (
    "tests/test_ordinary_formatting_review_service.py",
    "tests/test_ordinary_formatting_options.py",
)
# ASGI/browser tests use the standard synthetic pytest path: Windows asyncio
# requires a local socket pair, which this offline boundary deliberately denies.
TESTS += ORDINARY_SOURCE_TESTS + REVIEW_SERVICE_TESTS
MODEL_TESTS = ("tests/test_acceptance_model_selection.py", "tests/test_terra_client_selection.py",
               "tests/test_structured_acceptance_prepare.py", "tests/test_openai_structured_transport.py",
               "tests/test_openai_transport_retries.py")
PREPARATION_TESTS = ("tests/test_structured_acceptance_prepare.py",)
SUCCESSOR_TESTS = ("tests/test_acceptance_successor.py",)
LITERAL_TESTS = ("tests/test_structured_literal_contract.py", "tests/test_translation_structure.py",
                 "tests/test_structured_arabic_signature_abbreviation.py",
                 "tests/test_structured_arabic_wrapped_headers.py",
                 "tests/test_structured_arabic_entities.py",
                 "tests/test_structured_arabic_official_signatures.py",
                 "tests/test_structured_arabic_postal_blocks.py",
                 "tests/test_structured_arabic_witness_lists.py",
                 "tests/test_structured_arabic_source_names.py",
                 "tests/test_structured_arabic_literals.py", "tests/test_structured_glossary.py")


class OfflineBoundaryDenied(RuntimeError):
    """Only a content-free category is exposed."""


class OfflineBoundary:
    """Finite side-effect policy; no claims about unaudited native behavior."""

    def __init__(self, *, read_roots, write_root):
        self.read_roots = tuple(Path(p).resolve() for p in read_roots)
        self.write_root = Path(write_root).resolve()
        self.null_device = Path(os.devnull).resolve()
        self.denials: dict[str, int] = {}
        self.last_denial_context: dict[str, str] = {}

    def _deny(self, category):
        self.denials[category] = self.denials.get(category, 0) + 1
        raise OfflineBoundaryDenied(category)

    def _path(self, value, *, write=False, allow_null=False):
        # Python's own capture machinery reopens owned numeric descriptors.
        # Descriptor provenance is part of the trusted-runtime assumption.
        if isinstance(value, int):
            return
        if not isinstance(value, (str, bytes, os.PathLike)):
            self._deny("unsupported_path")
        path = Path(os.fsdecode(value)).resolve()
        if allow_null and path == self.null_device:
            return  # pytest capture's exact OS null device, never arbitrary devices.
        if not path.is_relative_to(self.write_root) and path.name.lower().startswith(".env"):
            self._deny("ambient_env_file")
        roots = (self.write_root,) if write else (*self.read_roots, self.write_root)
        if not any(path.is_relative_to(root) for root in roots):
            self.last_denial_context = {
                "denied_path": str(path),
                "path_class": "ancestor_of_allowed_root" if any(root.is_relative_to(path) for root in roots) else "outside_roots",
                "known_config_name": path.name if path.name in {
                    "pyproject.toml", "pytest.ini", ".pytest.ini", "tox.ini",
                    "setup.cfg", "conftest.py", "pyvenv.cfg", "sitecustomize.py",
                } else "not_an_allowlisted_config_name",
            }
            self._deny("write_outside_fixture" if write else "read_outside_scope")

    def _no_dir_fd(self, values):
        if any(value not in (None, -1) for value in values):
            self._deny("descriptor_relative_mutation")

    def check(self, event, args):
        if event in {
            "socket.connect", "socket.connect_ex", "socket.getaddrinfo",
            "socket.gethostbyname", "socket.gethostbyaddr", "socket.bind",
            "socket.sendto", "socket.sendmsg", "http.client.connect",
            "subprocess.Popen", "os.system", "os.startfile", "os.startfile/2",
            "os.exec", "os.posix_spawn", "os.fork", "os.forkpty",
        } or event.startswith("winreg."):
            self._deny("network_process_or_registry")
        if event == "import" and args and str(args[0]).split(".")[0] in {
            "win32com", "pythoncom", "comtypes",
        }:
            self._deny("native_automation_import")
        if event == "open":
            mode = args[1] if len(args) > 1 else None
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            writing = writing or isinstance(mode, str) and any(char in mode for char in "wax+")
            self._path(args[0], write=writing, allow_null=True)
        elif event in {"os.listdir", "os.scandir"}:
            self._path(args[0] if args and args[0] is not None else os.getcwd())
        elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate"}:
            offset = {"os.remove": 1, "os.rmdir": 1, "os.mkdir": 2,
                      "os.chmod": 2, "os.utime": 3, "os.truncate": 2}[event]
            self._no_dir_fd(args[offset:])
            self._path(args[0], write=True)
        elif event in {"os.rename", "os.link"}:
            self._no_dir_fd(args[2:])
            self._path(args[0], write=True)
            self._path(args[1], write=True)
        elif event == "os.symlink":
            self._no_dir_fd(args[2:])
            self._path(args[1], write=True)


def _prepare_environment(output: Path) -> None:
    # Child-process environment only. No real credential value is read or saved.
    for name in tuple(os.environ):
        upper = name.upper()
        if any(part in upper for part in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")) or upper in {
            "OPENAI_BASE_URL", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID", "HTTP_PROXY",
            "HTTPS_PROXY", "ALL_PROXY", "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
            "LEGALPDF_TRANSLATION_PROTOCOL",
        }:
            os.environ.pop(name, None)
    for name, suffix in (("APPDATA", "appdata"), ("LOCALAPPDATA", "localappdata"),
                         ("TEMP", "temp"), ("TMP", "temp")):
        directory = output / suffix
        directory.mkdir(exist_ok=True)
        os.environ[name] = str(directory)
    os.environ.update(
        OPENAI_API_KEY="synthetic-offline-key",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONDONTWRITEBYTECODE="1",
        QT_QPA_PLATFORM="offscreen",
    )
    sys.dont_write_bytecode = True


def isolated_import_paths(current, *, repository, runtime_roots):
    """Do not inherit another editable application checkout from a shared venv."""
    allowed = tuple(Path(root).resolve() for root in runtime_roots)
    repository = Path(repository).resolve()
    retained = []
    for item in current:
        if not item:
            continue
        resolved = Path(item).resolve()
        if any(resolved.is_relative_to(root) for root in allowed):
            retained.append(str(resolved))
    return [str(repository / "src"), str(repository), *dict.fromkeys(retained)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--suite", choices=("all", "caller", "boundary", "literals", "sdk", "recovery", "legacy_recovery", "preparation", "successor", "assembly", "models", "formatting", "ordinary_formatting", "ordinary_source", "review_services", "formatting_options", "formatted_assembly"), default="all")
    arguments = parser.parse_args(argv)
    selected_tests = {"all": TESTS, "caller": CALLER_TESTS, "boundary": BOUNDARY_TESTS,
                      "literals": LITERAL_TESTS, "sdk": SDK_TESTS, "recovery": RECOVERY_TESTS,
                      "legacy_recovery": LEGACY_RECOVERY_TESTS,
                      "preparation": PREPARATION_TESTS, "successor": SUCCESSOR_TESTS,
                      "assembly": ASSEMBLY_TESTS, "models": MODEL_TESTS,
                      "formatting": FORMATTING_TESTS,
                      "ordinary_formatting": ORDINARY_FORMATTING_TESTS,
                      "ordinary_source": ORDINARY_SOURCE_TESTS,
                      "review_services": REVIEW_SERVICE_TESTS,
                      "formatting_options": ("tests/test_ordinary_formatting_options.py",),
                      "formatted_assembly": FORMATTED_ASSEMBLY_TESTS}[arguments.suite]
    if Path(sys.executable).resolve() != CANONICAL_PYTHON.resolve():
        raise SystemExit("Use the canonical project .venv311 interpreter.")
    if not sys.flags.isolated:
        raise SystemExit("Use Python -I -B for isolated startup.")
    output = arguments.output_root
    if not output.is_absolute() or output.parent.resolve() != OUTPUT_PARENT.resolve():
        raise SystemExit("Output must be a new direct child of the private benchmark directory.")
    if not output.name.startswith("application_offline_acceptance_"):
        raise SystemExit("Unexpected output directory name.")
    # Exclusive creation ensures this invocation cannot reuse an earlier run.
    output.mkdir(exist_ok=False)
    output = output.resolve()
    _prepare_environment(output)
    os.chdir(REPOSITORY)
    sys.path[:] = isolated_import_paths(
        sys.path, repository=REPOSITORY, runtime_roots=(sys.prefix, sys.base_prefix))
    boundary = OfflineBoundary(
        read_roots=(REPOSITORY, Path(sys.prefix), Path(sys.base_prefix)),
        write_root=output,
    )
    sys.addaudithook(boundary.check)
    started = time.monotonic()
    def time_limit():
        try:
            with (output / "timeout.json").open("x", encoding="utf-8") as handle:
                json.dump({"status": "timeout", "limit_seconds": 600, "exit_code": 124}, handle)
        finally:
            os._exit(124)
    watchdog = threading.Timer(600, time_limit)
    watchdog.daemon = True
    watchdog.start()
    exit_code, failure, phase = 2, None, "application_import"
    try:
        import legalpdf_translate
        if Path(legalpdf_translate.__file__).resolve() != REPOSITORY / "src/legalpdf_translate/__init__.py":
            raise OfflineBoundaryDenied("wrong_application_import_origin")
        phase = "pytest_import"
        import pytest
        phase = "tests"
        exit_code = int(pytest.main([
            "-q", "-p", "no:cacheprovider", "--tb=short", "--maxfail=1",
            "-c", str(REPOSITORY / "pyproject.toml"),
            "--rootdir", str(REPOSITORY), "--confcutdir", str(REPOSITORY / "tests"),
            "--basetemp", str(output / "pytest"), *selected_tests,
        ]))
    except BaseException as exc:
        failure = type(exc).__name__
    finally:
        watchdog.cancel()
        if boundary.denials and exit_code == 0:
            exit_code = 2
            failure = "UnexpectedBoundaryDenial"
        report = {
            "profile": "trusted_runtime_offline_application_tests_v1",
            "scope": "synthetic_only_no_real_ledger_source_provider_or_native_automation",
            "historical_guard_result": "unchanged_not_revalidated",
            "hostile_native_sandbox": False,
            "interpreter": str(Path(sys.executable).resolve()),
            "repository": str(REPOSITORY),
            "tests": list(selected_tests),
            "exit_code": exit_code,
            "failure_class": failure,
            "phase": phase,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "python_audit_denials": dict(boundary.denials),
            "last_denial_context": dict(boundary.last_denial_context),
            "real_key_used": False,
            "paid_operation": False,
        }
        with (output / "result.json").open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
