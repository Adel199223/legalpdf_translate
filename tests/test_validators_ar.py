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


def test_validate_ar_accepts_matching_expected_tokens() -> None:
    text = f"الاسم: {LRI}[[Adel Belghali]]{PDI}"
    result = validate_ar(text, expected_tokens=["Adel Belghali"])
    assert result.ok is True


def test_validate_ar_accepts_extra_tokens_when_expected_tokens_match() -> None:
    text = f"الاسم: {LRI}[[Adel Belghali]]{PDI} {LRI}[[EXTRA-123]]{PDI}"
    result = validate_ar(text, expected_tokens=["Adel Belghali"])
    assert result.ok is True
    assert result.details is not None
    assert result.details["missing_count"] == 0
    assert result.details["unexpected_count"] == 1


def test_validate_ar_rejects_missing_expected_tokens() -> None:
    text = f"الاسم: {LRI}[[Adel Belghali]]{PDI}"
    result = validate_ar(text, expected_tokens=["Rua Luís de Camões no 6"])
    assert result.ok is False
    assert result.reason == "Expected locked token mismatch."
    assert result.details is not None
    assert result.details["missing_count"] == 1


def test_validate_ar_rejects_altered_expected_tokens() -> None:
    text = f"الاسم: {LRI}[[Adel Belghaly]]{PDI}"
    result = validate_ar(text, expected_tokens=["Adel Belghali"])
    assert result.ok is False
    assert result.reason == "Expected locked token mismatch."
    assert result.details is not None
    assert result.details["missing_count"] == 1
    assert result.details["altered_count"] == 1
