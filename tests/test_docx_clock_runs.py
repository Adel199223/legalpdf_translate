"""Clock punctuation must not become a separate RTL run between saved tokens."""

import pytest

from legalpdf_translate.docx_writer import (
    _segment_rtl_placeholder_aware_runs,
    sanitize_bidi_controls,
    unwrap_internal_placeholders,
)


def _protected(value: str, isolated: bool) -> str:
    return f"\u2066[[{value}]]\u2069" if isolated else f"[[{value}]]"


@pytest.mark.parametrize("clock", ["00:00", "09:30", "23:59", "00:00:00", "09:30:07", "23:59:59"])
@pytest.mark.parametrize("form", ["split", "whole", "plain", "mixed"])
@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("strip_controls", [False, True])
def test_complete_clock_stays_in_one_ltr_run(clock, form, isolated, strip_controls):
    components = clock.split(":")
    if form == "plain":
        value = clock
    elif form == "whole":
        value = _protected(clock, isolated)
    elif form == "mixed":
        value = _protected(components[0], isolated) + ":" + ":".join(components[1:])
    else:
        value = ":".join(_protected(part, isolated) for part in components)
    text = f"موعد الجلسة {value} ثم الحضور."
    runs, mixed = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=strip_controls)
    expected = unwrap_internal_placeholders(text)
    if strip_controls:
        expected = sanitize_bidi_controls(expected)
    assert "".join(chunk for _, chunk in runs) == expected
    assert mixed
    assert any(kind == "ltr" and sanitize_bidi_controls(chunk) == clock for kind, chunk in runs)
    assert not any(kind == "rtl" and ":" in chunk for kind, chunk in runs)


@pytest.mark.parametrize("value", [
    "[[24]]:[[00]]", "[[09]]:[[60]]", "[[09]]:[[30]]:[[99]]",
    "[[09]]:[[30]]:[[00]]:[[12]]", "[[009]]:[[30]]", "[[09]]:[[300]]",
    "[[9]]:[[30]]", "[[09]]:[[3]]", "A[[09]]:[[30]]", "[[09]]:[[30]]B",
    "_[[09]]:[[30]]", "[[09]]:[[30]]_", "1[[09]]:[[30]]", "[[09]]:[[30]]1",
    "[[09]] : [[30]]", "[[09]]\t:\t[[30]]", "[[09]]\n:[[30]]",
    "[[09]]:\r\n[[30]]", "[[09]] و:[[30]]", "[[AA]]:[[BB]]",
    "[[[09]]:[[30]]]",
    "12.[[09]]:[[30]]", "[[09]]:[[30]].5", "ABC-[[09]]:[[30]]",
    "A\u0301[[09]]:[[30]]", "[[09]]:[[30]]\u0301B", "ABC/[[09]]:[[30]]",
])
@pytest.mark.parametrize("strip_controls", [False, True])
def test_nonclock_or_ambiguous_boundaries_keep_existing_direction(value, strip_controls):
    text = f"النص {value} نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=strip_controls)
    expected = unwrap_internal_placeholders(text)
    if strip_controls:
        expected = sanitize_bidi_controls(expected)
    assert "".join(chunk for _, chunk in runs) == expected
    # These saved split-token separators have no complete supported clock span.
    assert any(kind == "rtl" and ":" in chunk for kind, chunk in runs)


@pytest.mark.parametrize("strip_controls", [False, True])
def test_seconds_across_partial_whole_token_and_distinct_clocks(strip_controls):
    text = "موعد \u2066[[09:30]]\u2069:\u2066[[07]]\u2069 وآخر [[23]]:[[59]]"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=strip_controls)
    clocks = [sanitize_bidi_controls(chunk) for kind, chunk in runs if kind == "ltr"]
    assert clocks == ["09:30:07", "23:59"]
    assert not any(kind == "rtl" and ":" in chunk for kind, chunk in runs)


def test_only_clock_colons_change_not_label_name_or_legal_punctuation():
    text = "الموعد: [[09]]:[[30]]؛ الاسم: [[João Guerreiro]]، رقم [[14-10-2026]] مبلغ [[150,00]]"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=True)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    ltr = [chunk for kind, chunk in runs if kind == "ltr"]
    assert ltr == ["09:30", "João Guerreiro", "14-10-2026", "150,00"]
    assert sum(chunk.count(":") for kind, chunk in runs if kind == "rtl") == 2


def test_no_numeric_grouping_across_whitespace_only_boundary():
    runs, _ = _segment_rtl_placeholder_aware_runs("الموعد [[09]] [[30]] ثم [[14]]/[[2]]", strip_bidi_controls=True)
    assert ("ltr", "09 30") not in runs
    assert ("rtl", " ") in runs
    # Closed numeric references have their own independent slash rule.
    assert ("ltr", "14/2") in runs


@pytest.mark.parametrize("value", ["[[09]]:[[30]", "[[09]]:30]]"])
def test_malformed_wrappers_are_not_repaired_or_promoted_to_clock(value):
    text = f"النص {value} نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=True)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert ("ltr", "09:30") not in runs


@pytest.mark.parametrize("control", ["\u061c", "\u200f", "\u202a", "\u202b", "\u202d", "\u202e", "\u2067", "\u2068"])
@pytest.mark.parametrize("location", ["start", "inside", "end"])
def test_conflicting_retained_controls_leave_clock_punctuation_unchanged(control, location):
    clock = "[[09]]:[[30]]"
    if location == "start":
        clock = control + clock
    elif location == "end":
        clock += control
    else:
        clock = "[[09]]:" + control + "[[30]]"
    text = "الموعد " + clock + " نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=False)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert any(kind == "rtl" and ":" in chunk for kind, chunk in runs)
    # Explicit stripping is still allowed by the existing option.
    stripped, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=True)
    assert ("ltr", "09:30") in stripped
