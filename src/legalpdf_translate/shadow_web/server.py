"""CLI entrypoint for the local LegalPDF Translate browser app."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import nullcontext
import os
from pathlib import Path
import sys
import threading
import webbrowser

import uvicorn

from legalpdf_translate.build_identity import detect_runtime_build_identity
from legalpdf_translate.shadow_runtime import (
    SHADOW_DEFAULT_PORT,
    SHADOW_HOST,
    classify_shadow_listener,
    detect_shadow_runtime_paths,
    load_shadow_runtime_metadata,
)
from legalpdf_translate.shadow_web.app import create_shadow_app

_DEFAULT_BROWSER_WORKSPACE = "workspace-1"


def _default_browser_url(port: int) -> str:
    return f"http://{SHADOW_HOST}:{int(port)}/?mode=live&workspace={_DEFAULT_BROWSER_WORKSPACE}#new-job"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local LegalPDF Translate browser app.")
    parser.add_argument("--host", default=SHADOW_HOST, help="Bind host. Defaults to 127.0.0.1 only.")
    parser.add_argument("--port", type=int, default=SHADOW_DEFAULT_PORT, help="Bind port. Defaults to 8877.")
    parser.add_argument("--open", action="store_true", help="Open the browser after startup.")
    return parser


def _configure_windows_asyncio_policy() -> None:
    """Avoid Proactor/h11 shutdown crashes on malformed local requests."""
    if not sys.platform.startswith("win"):
        return
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is None:
        return
    if isinstance(asyncio.get_event_loop_policy(), selector_policy):
        return
    asyncio.set_event_loop_policy(selector_policy())


def _run_browser_server(app, *, port: int) -> None:
    config = uvicorn.Config(
        app,
        host=SHADOW_HOST,
        port=int(port),
        log_level="info",
        loop="asyncio",
        http="h11",
    )
    server = uvicorn.Server(config)
    if sys.platform.startswith("win"):
        server.install_signal_handlers = lambda: None
        server.capture_signals = nullcontext  # type: ignore[assignment]
    server.run()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if str(args.host).strip() != SHADOW_HOST:
        raise SystemExit("Shadow web must bind only to 127.0.0.1.")

    repo_root = Path(__file__).resolve().parents[3]
    build_identity = detect_runtime_build_identity(repo=repo_root, labels=("shadow-web",))
    runtime_paths = detect_shadow_runtime_paths(repo=repo_root, identity=build_identity)
    listener = classify_shadow_listener(port=int(args.port), expected_pid=os.getpid())
    if listener.status == "unavailable":
        existing_metadata = load_shadow_runtime_metadata(runtime_paths.runtime_metadata_path)
        existing_pid = None
        if isinstance(existing_metadata, dict):
            try:
                existing_pid = int(existing_metadata.get("pid", 0))
            except (TypeError, ValueError):
                existing_pid = None
        if existing_pid is not None and existing_pid == listener.pid:
            if args.open:
                webbrowser.open(_default_browser_url(int(args.port)), new=1)
            return 0
        raise SystemExit(
            f"Shadow web listener unavailable on http://{SHADOW_HOST}:{int(args.port)}/ "
            f"(owned by PID {listener.pid})."
        )

    if args.open:
        threading.Timer(
            1.0,
            lambda: webbrowser.open(_default_browser_url(int(args.port)), new=1),
        ).start()

    _configure_windows_asyncio_policy()
    app = create_shadow_app(repo_root=repo_root, port=int(args.port))
    _run_browser_server(app, port=int(args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
