from __future__ import annotations

from legalpdf_translate.image_io import should_include_image
from legalpdf_translate.types import ImageMode, TargetLang


def test_enfr_auto_image_strict() -> None:
    assert should_include_image(
        ImageMode.AUTO,
        "x" * 19,
        False,
        fragmented=False,
        lang=TargetLang.EN,
    )
    assert should_include_image(
        ImageMode.AUTO,
        "x" * 20,
        False,
        fragmented=False,
        lang=TargetLang.FR,
    ) is False
    # EN/FR should ignore fragmentation/newline heuristics for auto image attachment.
    assert should_include_image(
        ImageMode.AUTO,
        ("a\n" * 150) + "tail",
        False,
        fragmented=True,
        lang=TargetLang.EN,
    ) is False
    assert should_include_image(
        ImageMode.AUTO,
        "normal extracted text content over threshold",
        True,
        fragmented=False,
        lang=TargetLang.FR,
    )


def test_ar_auto_image_keeps_fragmentation_heuristics() -> None:
    assert should_include_image(
        ImageMode.AUTO,
        ("x\n" * 200) + "z",
        False,
        fragmented=False,
        lang=TargetLang.AR,
    )
    assert should_include_image(
        ImageMode.AUTO,
        "readable arabic-like extracted text content long enough to avoid short threshold",
        False,
        fragmented=False,
        lang=TargetLang.AR,
    ) is False


def test_force_include_overrides_mode_off() -> None:
    assert should_include_image(
        ImageMode.OFF,
        "readable text",
        False,
        fragmented=False,
        lang=TargetLang.FR,
        force_include=True,
    ) is True
