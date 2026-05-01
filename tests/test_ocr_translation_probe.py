from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

TOOLING_ROOT = Path(__file__).resolve().parents[1] / "tooling"
if str(TOOLING_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLING_ROOT))

import ocr_translation_probe as probe_tool

from legalpdf_translate.types import TargetLang


def test_parse_pages_spec_supports_ranges_and_singletons() -> None:
    assert probe_tool.parse_pages_spec("1-2,4,6-7", page_count=7) == [1, 2, 4, 6, 7]


def test_build_safe_probe_config_locks_runtime_safe_settings(tmp_path: Path) -> None:
    config = probe_tool.build_safe_probe_config(
        pdf_path=tmp_path / "doc.pdf",
        outdir=tmp_path / "out",
        lang=TargetLang.AR,
        pages=[1, 2],
        settings={"ocr_api_key_env_name": "OPENAI_API_KEY", "ocr_api_model": "gpt-5.2"},
    )
    assert config.ocr_mode.value == "always"
    assert config.ocr_engine.value == "api"
    assert config.image_mode.value == "off"
    assert config.workers == 1
    assert config.resume is False
    assert config.keep_intermediates is True
    assert config.effort_policy.value == "fixed_high"
    assert config.start_page == 1
    assert config.end_page == 2


def test_build_safe_probe_config_defaults_openai_env_name(tmp_path: Path) -> None:
    config = probe_tool.build_safe_probe_config(
        pdf_path=tmp_path / "doc.pdf",
        outdir=tmp_path / "out",
        lang=TargetLang.AR,
        pages=[1],
        settings={},
    )
    assert config.ocr_api_key_env_name == "OPENAI_API_KEY"


def test_collect_probe_packet_passes_effective_ocr_env_name_to_preflight(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")
    captured_env: dict[str, str] = {}

    def _run_ocr_preflight(*, environment):
        captured_env.update(environment)
        return {
            "tool": "ocr_preflight",
            "overall_status": "available",
            "fallback_readiness": {"local_only": "available", "local_then_api_required_only": "available"},
        }

    monkeypatch.setattr(probe_tool, "run_ocr_preflight", _run_ocr_preflight)
    monkeypatch.setattr(
        probe_tool,
        "load_gui_settings",
        lambda: {"ocr_api_provider": "gemini", "ocr_api_key_env_name": "GEMINI_API_KEY"},
    )
    monkeypatch.setattr(probe_tool, "get_page_count", lambda _pdf: 2)
    monkeypatch.setattr(
        probe_tool,
        "extract_ordered_page_text",
        lambda _pdf, _idx: SimpleNamespace(text="header", extraction_failed=False, fragmented=False),
    )

    probe_tool.collect_probe_packet(
        pdf_path=pdf_path,
        lang=TargetLang.FR,
        outdir=tmp_path / "out",
        pages=[1],
        run_workflow=False,
        environment={},
    )

    assert captured_env["OCR_API_KEY_ENV_NAME"] == "GEMINI_API_KEY"


def test_collect_probe_packet_without_workflow_run(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        probe_tool,
        "run_ocr_preflight",
        lambda *, environment: {
            "tool": "ocr_preflight",
            "overall_status": "unavailable",
            "fallback_readiness": {"local_only": "unavailable", "local_then_api_required_only": "unavailable"},
        },
    )
    monkeypatch.setattr(probe_tool, "load_gui_settings", lambda: {"ocr_api_key_env_name": "OPENAI_API_KEY"})
    monkeypatch.setattr(probe_tool, "get_page_count", lambda _pdf: 7)
    monkeypatch.setattr(
        probe_tool,
        "extract_ordered_page_text",
        lambda _pdf, _idx: SimpleNamespace(text="", extraction_failed=True, fragmented=False),
    )

    packet = probe_tool.collect_probe_packet(
        pdf_path=pdf_path,
        lang=TargetLang.AR,
        outdir=tmp_path / "out",
        pages=[1, 2],
        run_workflow=False,
        environment={},
    )

    assert packet["inspection"]["page_count"] == 7
    assert packet["inspection"]["direct_extraction_failed"] is True
    assert packet["recommended_settings"]["ocr_engine"] == "api"
    assert packet["workflow_probe"] is None
    assert "--image-mode" in packet["recommended_cli_args"]


def test_collect_probe_packet_runs_workflow_when_requested(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        probe_tool,
        "run_ocr_preflight",
        lambda *, environment: {
            "tool": "ocr_preflight",
            "overall_status": "degraded",
            "fallback_readiness": {"local_only": "degraded", "local_then_api_required_only": "available"},
        },
    )
    monkeypatch.setattr(probe_tool, "load_gui_settings", lambda: {})
    monkeypatch.setattr(probe_tool, "get_page_count", lambda _pdf: 4)
    monkeypatch.setattr(
        probe_tool,
        "extract_ordered_page_text",
        lambda _pdf, _idx: SimpleNamespace(text="header", extraction_failed=False, fragmented=False),
    )

    captured: dict[str, object] = {}

    class _FakeWorkflow:
        def run(self, config):  # type: ignore[no-untyped-def]
            captured["config"] = config
            return SimpleNamespace(
                success=True,
                exit_code=0,
                error=None,
                completed_pages=2,
                run_dir=tmp_path / "run_dir",
                run_summary_path=tmp_path / "run_dir" / "run_summary.json",
            )

    monkeypatch.setattr(probe_tool, "TranslationWorkflow", _FakeWorkflow)

    packet = probe_tool.collect_probe_packet(
        pdf_path=pdf_path,
        lang=TargetLang.FR,
        outdir=tmp_path / "out",
        pages=[1, 2],
        run_workflow=True,
        environment={},
    )

    config = captured["config"]
    assert config.image_mode.value == "off"
    assert config.ocr_engine.value == "api"
    assert packet["workflow_probe"]["success"] is True
