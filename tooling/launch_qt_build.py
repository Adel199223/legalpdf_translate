from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legalpdf_translate.build_identity import (  # noqa: E402
    canonical_build_config_path,
    current_branch,
    current_head_sha,
    head_contains_floor,
    load_canonical_build_config,
    try_load_canonical_build_config,
    normalize_path_identity,
    parse_build_labels,
)
from legalpdf_translate.runtime_health import (  # noqa: E402
    CRITICAL_APP_IMPORTS,
    CRITICAL_RUNTIME_IMPORTS,
    DEGRADED_RUNTIME_REASON_ENV,
)


class LaunchError(RuntimeError):
    pass


_WSL_MNT_RE = re.compile(r'^/mnt/([A-Za-z])/(.*)$')


def _to_windows_path(path: str | Path) -> str:
    resolved = Path(path).expanduser()
    text = str(resolved.resolve()) if resolved.exists() else str(resolved)
    if len(text) >= 3 and text[1:3] == ':\\':
        return text
    if text.startswith('/mnt/') and len(text) > 6:
        drive = text[5].upper()
        tail = text[7:].replace('/', '\\')
        return f'{drive}:\\{tail}' if tail else f'{drive}:\\'
    return text.replace('/', '\\')


def _coerce_repo_path(path_text: str | Path) -> Path:
    text = str(path_text).strip()
    match = _WSL_MNT_RE.match(text)
    if match:
        drive = match.group(1).upper()
        tail = match.group(2).replace('/', '\\')
        return Path(f'{drive}:\\{tail}')
    return Path(text).expanduser()


def _python_candidates_for(worktree: Path) -> list[Path]:
    resolved_worktree = worktree.expanduser().resolve()
    roots: list[Path] = [resolved_worktree]
    config = try_load_canonical_build_config(resolved_worktree)
    if config is not None:
        canonical_root = _coerce_repo_path(config.canonical_worktree_path).resolve()
        if canonical_root not in roots:
            roots.append(canonical_root)
    candidates: list[Path] = []
    for root in roots:
        candidates.extend(
            [
                root / '.venv311' / 'Scripts' / 'pythonw.exe',
                root / '.venv311' / 'Scripts' / 'python.exe',
                root / '.venv' / 'Scripts' / 'pythonw.exe',
                root / '.venv' / 'Scripts' / 'python.exe',
            ]
        )
    return candidates


def _python_executable_for(worktree: Path) -> Path:
    candidates = _python_candidates_for(worktree)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise LaunchError(
        f'No Windows Python launcher found for worktree: {worktree}. '
        'Expected .venv311/Scripts/pythonw.exe or python.exe in the target worktree '
        'or its canonical worktree.'
    )


def _python_executable_or_placeholder(worktree: Path) -> str:
    try:
        return str(_python_executable_for(worktree))
    except LaunchError:
        placeholder = _python_candidates_for(worktree)[0]
        return str(placeholder)


def _probe_python_executable(python_exe: Path) -> Path:
    if python_exe.name.lower() == 'pythonw.exe':
        probe = python_exe.with_name('python.exe')
        if probe.exists():
            return probe
    return python_exe


def _runtime_preflight_env(worktree: Path) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str((worktree / 'src').resolve())
    existing = str(env.get('PYTHONPATH', '') or '').strip()
    env['PYTHONPATH'] = (
        pythonpath if existing == '' else os.pathsep.join([pythonpath, existing])
    )
    env.pop(DEGRADED_RUNTIME_REASON_ENV, None)
    return env


def _runtime_preflight_code() -> str:
    modules = [*CRITICAL_RUNTIME_IMPORTS, *CRITICAL_APP_IMPORTS]
    return textwrap.dedent(
        f"""
        import importlib
        import json
        import sys

        modules = {json.dumps(modules)}
        failed = []
        for name in modules:
            try:
                importlib.import_module(name)
            except Exception as exc:
                failed.append({{"module": name, "error": f"{{type(exc).__name__}}: {{exc}}"}})
        print(json.dumps({{"failed_imports": failed}}))
        raise SystemExit(0 if not failed else 1)
        """
    ).strip()


def _run_runtime_preflight(python_exe: Path, worktree: Path) -> dict[str, object]:
    probe_exe = _probe_python_executable(python_exe)
    proc = subprocess.run(
        [str(probe_exe), '-c', _runtime_preflight_code()],
        cwd=worktree,
        env=_runtime_preflight_env(worktree),
        text=True,
        capture_output=True,
        check=False,
    )
    stdout = proc.stdout.strip()
    payload: dict[str, object] = {}
    if stdout:
        try:
            payload = json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError:
            payload = {'failed_imports': [], 'raw_stdout': stdout}
    failed_imports = payload.get('failed_imports', [])
    if proc.returncode != 0 or failed_imports:
        lines = [
            f'Runtime preflight failed for {python_exe}.',
            'The selected runtime is missing required imports and would launch a degraded or broken GUI session.',
        ]
        if isinstance(failed_imports, list):
            for item in failed_imports:
                if not isinstance(item, dict):
                    continue
                module_name = str(item.get('module', '')).strip()
                error_text = str(item.get('error', '')).strip()
                if module_name and error_text:
                    lines.append(f'- {module_name}: {error_text}')
        stderr = proc.stderr.strip()
        raw_stdout = str(payload.get('raw_stdout', '')).strip()
        if stderr:
            lines.append(f'stderr: {stderr}')
        elif raw_stdout:
            lines.append(f'stdout: {raw_stdout}')
        lines.append('Repair the selected Python 3.11 / .venv311 before launching.')
        raise LaunchError('\n'.join(lines))
    return {
        'status': 'ok',
        'probe_python_executable': str(probe_exe),
        'checked_modules': [*CRITICAL_RUNTIME_IMPORTS, *CRITICAL_APP_IMPORTS],
    }


def _coerce_input_path(path_text: str) -> str:
    text = path_text.strip()
    if text.startswith('/mnt/') and len(text) > 6:
        drive = text[5].upper()
        tail = text[7:].replace('/', '\\')
        return f'{drive}:\\{tail}' if tail else f'{drive}:\\'
    return text


def _validate_worktree(path_text: str) -> Path:
    worktree = Path(_coerce_input_path(path_text)).expanduser().resolve()
    if not worktree.exists() or not worktree.is_dir():
        raise LaunchError(f'Invalid worktree path: {worktree}')
    entrypoint = worktree / 'src' / 'legalpdf_translate' / 'qt_app.py'
    if not entrypoint.exists():
        raise LaunchError(f'Missing Qt entrypoint in worktree: {entrypoint}')
    return worktree


def _build_identity_packet(
    worktree: Path,
    labels: tuple[str, ...],
    *,
    resolve_python: bool,
) -> dict[str, object]:
    config = load_canonical_build_config(REPO_ROOT)
    branch = current_branch(worktree)
    head_sha = current_head_sha(worktree)
    worktree_norm = normalize_path_identity(worktree)
    canonical_norm = normalize_path_identity(config.canonical_worktree_path)
    reasons: list[str] = []
    lineage_valid = head_contains_floor(worktree, config.approved_base_head_floor)
    if worktree_norm != canonical_norm:
        reasons.append(
            f'worktree {worktree_norm} does not match canonical worktree {canonical_norm}'
        )
    if branch != config.canonical_branch:
        reasons.append(
            f'branch {branch} does not match canonical branch {config.canonical_branch}'
        )
    if not lineage_valid:
        reasons.append(
            f'HEAD does not contain approved base floor {config.approved_base_head_floor}'
        )
    if not head_contains_floor(worktree, config.canonical_head_floor):
        reasons.append(
            f'HEAD does not contain canonical floor {config.canonical_head_floor}'
        )
    python_exe = (
        str(_python_executable_for(worktree))
        if resolve_python
        else _python_executable_or_placeholder(worktree)
    )
    return {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'worktree_path': str(worktree),
        'branch': branch,
        'head_sha': head_sha,
        'entrypoint_module': 'legalpdf_translate.qt_app',
        'python_executable': python_exe,
        'launch_command': [python_exe, '-m', 'legalpdf_translate.qt_app'],
        'labels': list(labels),
        'is_canonical': not reasons,
        'is_lineage_valid': lineage_valid,
        'canonical_worktree_path': config.canonical_worktree_path,
        'canonical_branch': config.canonical_branch,
        'approved_base_branch': config.approved_base_branch,
        'approved_base_head_floor': config.approved_base_head_floor,
        'canonical_head_floor': config.canonical_head_floor,
        'allow_noncanonical_by_flag': config.allow_noncanonical_by_flag,
        'noncanonical_reasons': reasons,
    }


def _launch_windows(packet: dict[str, object]) -> None:
    if os.name != 'nt' and not shutil.which('powershell.exe'):
        raise LaunchError('Windows GUI launch requires powershell.exe.')
    worktree = Path(str(packet['worktree_path']))
    python_exe = Path(str(packet['python_executable']))
    pythonpath = str((worktree / 'src').resolve())
    labels = ','.join(str(item) for item in packet['labels'])
    config_path = canonical_build_config_path(REPO_ROOT)
    ps_command = (
        f"$env:PYTHONPATH={json.dumps(_to_windows_path(pythonpath))}; "
        f"$env:LEGALPDF_BUILD_LABELS={json.dumps(labels)}; "
        f"$env:LEGALPDF_CANONICAL_BUILD_CONFIG={json.dumps(_to_windows_path(config_path))}; "
        "Remove-Item Env:LEGALPDF_DEGRADED_RUNTIME_REASON -ErrorAction SilentlyContinue; "
        f"Start-Process -FilePath {json.dumps(_to_windows_path(python_exe))} "
        f"-WorkingDirectory {json.dumps(_to_windows_path(worktree))} "
        f"-ArgumentList @('-m','legalpdf_translate.qt_app')"
    )
    subprocess.run(
        ['powershell.exe', '-NoProfile', '-Command', ps_command],
        check=True,
        text=True,
        capture_output=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Launch a Qt build with explicit identity metadata.')
    parser.add_argument('--worktree', required=True, help='Absolute path to the target worktree.')
    parser.add_argument('--labels', default='', help='Optional comma-separated feature labels.')
    parser.add_argument('--identity-out', help='Optional JSON output path for the identity packet.')
    parser.add_argument('--allow-noncanonical', action='store_true', help='Allow launching a noncanonical worktree explicitly.')
    parser.add_argument('--dry-run', action='store_true', help='Print the identity packet without launching the app.')
    return parser.parse_args()


def main() -> int:
    try:
        args = _parse_args()
        worktree = _validate_worktree(args.worktree)
        labels = parse_build_labels(args.labels)
        packet = _build_identity_packet(worktree, labels, resolve_python=not args.dry_run)
        if not packet['is_lineage_valid']:
            raise LaunchError(
                'Refusing to launch worktree that does not contain the approved base floor. '
                + ' '.join(str(item) for item in packet['noncanonical_reasons'])
            )
        if not packet['is_canonical'] and not args.allow_noncanonical:
            raise LaunchError(
                'Refusing to launch noncanonical worktree without --allow-noncanonical. '
                + ' '.join(str(item) for item in packet['noncanonical_reasons'])
            )
        if args.dry_run:
            packet['runtime_preflight'] = {'status': 'skipped', 'reason': 'dry-run'}
        else:
            packet['runtime_preflight'] = _run_runtime_preflight(
                Path(str(packet['python_executable'])),
                worktree,
            )
        packet['dry_run'] = bool(args.dry_run)
        packet['allow_noncanonical'] = bool(args.allow_noncanonical)
        payload = json.dumps(packet, indent=2)
        if args.identity_out:
            out_path = Path(args.identity_out).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + '\n', encoding='utf-8')
        print(payload)
        if args.dry_run:
            return 0
        _launch_windows(packet)
        return 0
    except LaunchError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f'Unexpected launch failure: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
