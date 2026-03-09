from __future__ import annotations

from types import SimpleNamespace

import legalpdf_translate.ocr_engine as ocr_engine_module
from legalpdf_translate.ocr_engine import LocalTesseractEngine


def _completed(code: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        returncode=code,
        stdout=stdout.encode("utf-8"),
        stderr=stderr.encode("utf-8"),
    )


def test_local_pass_a_short_circuits_when_quality_high(monkeypatch) -> None:
    monkeypatch.setattr(ocr_engine_module, "which", lambda _name: "/usr/bin/tesseract")
    calls: list[list[str]] = []

    def _run(command, capture_output, check, timeout):  # type: ignore[no-untyped-def]
        _ = capture_output, check, timeout
        calls.append(command)
        long_text = "\n".join(
            [
                "This legal OCR output line is intentionally verbose and alphanumeric rich for scoring.",
            ]
            * 18
        )
        return _completed(
            0,
            long_text,
            "",
        )

    monkeypatch.setattr(ocr_engine_module.subprocess, "run", _run)

    engine = LocalTesseractEngine(strict_unavailable=True)
    result = engine.ocr_image(b"fake-bytes", lang_hint="pt_latin_default")
    assert result.chars > 0
    assert result.selected_pass == "pass_a_document"
    assert result.quality_score >= 0.0
    assert len(calls) == 1
    assert "por+eng+fra" in calls[0]
    assert "--psm" in calls[0]
    assert "6" in calls[0]


def test_local_pass_b_selected_when_a_is_too_weak(monkeypatch) -> None:
    monkeypatch.setattr(ocr_engine_module, "which", lambda _name: "/usr/bin/tesseract")
    calls: list[list[str]] = []

    def _run(command, capture_output, check, timeout):  # type: ignore[no-untyped-def]
        _ = capture_output, check, timeout
        calls.append(command)
        psm = command[command.index("--psm") + 1]
        if psm == "6":
            return _completed(0, "x", "")
        return _completed(0, "Readable fallback output from sparse mode with many words and lines.", "")

    monkeypatch.setattr(ocr_engine_module.subprocess, "run", _run)

    engine = LocalTesseractEngine(strict_unavailable=True)
    result = engine.ocr_image(b"fake-bytes", lang_hint="pt_latin_default")
    assert result.chars > 0
    assert result.selected_pass == "pass_b_sparse"
    assert len(calls) == 2


def test_ar_track_runs_extra_pass_and_can_select_it(monkeypatch) -> None:
    monkeypatch.setattr(ocr_engine_module, "which", lambda _name: "/usr/bin/tesseract")
    calls: list[list[str]] = []

    def _run(command, capture_output, check, timeout):  # type: ignore[no-untyped-def]
        _ = capture_output, check, timeout
        calls.append(command)
        lang = command[command.index("-l") + 1]
        psm = command[command.index("--psm") + 1]
        if lang == "ara+eng" and psm == "6":
            return _completed(0, "النص العربي واضح وكامل مع إشارات تنظيمية جيدة", "")
        return _completed(0, "x", "")

    monkeypatch.setattr(ocr_engine_module.subprocess, "run", _run)

    engine = LocalTesseractEngine(strict_unavailable=True)
    result = engine.ocr_image(b"fake-bytes", lang_hint="ar_track_default")
    assert result.chars > 0
    assert result.selected_pass == "pass_c_ar_track"
    assert len(calls) == 3
    assert any("ara+eng" in call for call in calls)


def test_local_result_below_threshold_is_marked_unusable(monkeypatch) -> None:
    monkeypatch.setattr(ocr_engine_module, "which", lambda _name: "/usr/bin/tesseract")

    def _run(command, capture_output, check, timeout):  # type: ignore[no-untyped-def]
        _ = command, capture_output, check, timeout
        return _completed(0, "x", "")

    monkeypatch.setattr(ocr_engine_module.subprocess, "run", _run)

    engine = LocalTesseractEngine(strict_unavailable=True)
    result = engine.ocr_image(b"fake-bytes", lang_hint="pt_latin_default")
    assert result.chars == 0
    assert "below acceptance threshold" in str(result.failed_reason or "")
