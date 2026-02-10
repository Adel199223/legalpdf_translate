from legalpdf_translate.output_normalize import LRI, PDI
from legalpdf_translate.validators import validate_ar


def test_validate_ar_rejects_unwrapped_tokens() -> None:
    result = validate_ar("نص [[ABC]]")
    assert result.ok is False


def test_validate_ar_rejects_digits_outside_tokens() -> None:
    result = validate_ar("النص 123")
    assert result.ok is False


def test_validate_ar_rejects_latin_outside_tokens() -> None:
    result = validate_ar("النص ABC")
    assert result.ok is False


def test_validate_ar_accepts_wrapped_tokens() -> None:
    text = f"النص {LRI}[[ABC-123]]{PDI} فقط"
    result = validate_ar(text)
    assert result.ok is True
