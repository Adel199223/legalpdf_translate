from legalpdf_translate.validators import validate_enfr


def test_validate_enfr_accepts_non_empty_output() -> None:
    result = validate_enfr("Line one\nLine two")
    assert result.ok is True


def test_validate_enfr_rejects_empty_output() -> None:
    result = validate_enfr("   ")
    assert result.ok is False


def test_validate_enfr_rejects_blank_line() -> None:
    result = validate_enfr("Line one\n\nLine two")
    assert result.ok is False
