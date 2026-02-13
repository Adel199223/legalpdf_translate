from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import legalpdf_translate.calibration_audit as calibration_audit
from legalpdf_translate.ocr_engine import OcrResult
from legalpdf_translate.types import ImageMode, OcrEnginePolicy, OcrMode, ReasoningEffort, RunConfig, TargetLang


@dataclass
class _FakeApiResult:
    raw_output: str


class _FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def create_page_response(self, **_kwargs):  # type: ignore[no-untyped-def]
        if not self._responses:
            raise AssertionError("No more fake responses configured.")
        return _FakeApiResult(raw_output=self._responses.pop(0))


@dataclass
class _FakeOrdered:
    text: str
    extraction_failed: bool = False
    fragmented: bool = False


def test_pick_sample_pages_is_reproducible() -> None:
    first = calibration_audit.pick_sample_pages(20, 5, "seed-material", user_seed="abc")
    second = calibration_audit.pick_sample_pages(20, 5, "seed-material", user_seed="abc")
    third = calibration_audit.pick_sample_pages(20, 5, "seed-material", user_seed="xyz")

    assert first == second
    assert first != third
    assert len(first) == 5


def test_run_calibration_audit_retries_verifier_json_and_uses_forced_ocr_path(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%test\n")
    config = RunConfig(
        pdf_path=pdf_path,
        output_dir=tmp_path,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.LOCAL_THEN_API,
    )
    monkeypatch.setattr(calibration_audit, "get_page_count", lambda _path: 2)
    monkeypatch.setattr(calibration_audit, "extract_ordered_page_text", lambda _path, _idx: _FakeOrdered("source text"))
    monkeypatch.setattr(calibration_audit, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(calibration_audit, "should_include_image", lambda *args, **kwargs: False)
    fake_engine = object()
    monkeypatch.setattr(calibration_audit, "build_ocr_engine", lambda _cfg: fake_engine)
    forced_calls: list[tuple[object, str]] = []

    def _fake_ocr_pdf_page_text(_pdf, _page, mode, engine, **_kwargs):  # type: ignore[no-untyped-def]
        forced_calls.append((engine, mode.value))
        return OcrResult(text="ocr source", engine="local", failed_reason=None, chars=10)

    monkeypatch.setattr(calibration_audit, "ocr_pdf_page_text", _fake_ocr_pdf_page_text)
    client = _FakeClient(
        [
            "```\ntranslated output\n```",
            "not-json",
            '{"findings":[{"issue_type":"mistranslation","severity":"high","evidence":"x","explanation":"bad term","recommended_fix":"use glossary"}],"glossary_suggestions":[{"source_text":"acusação","preferred_translation":"indictment","target_lang":"EN","source_lang":"PT","match_mode":"exact","tier":2}],"prompt_addendum_suggestion":"Prefer legal register."}',
        ]
    )

    result = calibration_audit.run_calibration_audit(
        config=config,
        personal_glossaries_by_lang={"EN": [], "FR": [], "AR": []},
        project_glossaries_by_lang={"EN": [], "FR": [], "AR": []},
        enabled_tiers_by_lang={"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]},
        prompt_addendum_by_lang={"EN": "", "FR": "", "AR": ""},
        sample_pages=1,
        client=client,  # type: ignore[arg-type]
    )

    report = result["report"]
    suggestions = result["suggestions"]
    assert report["sampled_pages"]
    assert len(report["findings"]) == 1
    assert report["findings"][0]["issue_type"] == "mistranslation"
    assert len(suggestions["glossary_suggestions"]) == 1
    assert suggestions["prompt_addendum_suggestions"] == ["Prefer legal register."]
    assert any(call_engine is fake_engine and mode_value == "always" for call_engine, mode_value in forced_calls)
    assert Path(result["report_json_path"]).exists()
    assert Path(result["report_md_path"]).exists()
    assert Path(result["suggestions_json_path"]).exists()
