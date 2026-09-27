import json

import pytest

from legalpdf_translate.pricing import nonnegative_decimal, translation_fee_eur
from legalpdf_translate.user_settings import load_joblog_settings_from_path


@pytest.mark.parametrize("words,rate,total", [
    (1501, ".027", 40.53), (1138, "0,027", 30.73), (15, .027, .41),
    (5, ".027", .14), (1138, .08, 91.04), (0, .027, 0), (1, 0, 0),
    (100, "2.7e-2", 2.7),
])
def test_decimal_fee_rounds_half_up(words, rate, total):
    assert translation_fee_eur(words, rate) == total


@pytest.mark.parametrize("value", [True, False, -1, "-0.027", "NaN", "inf", "1e999", None, ""])
def test_invalid_rate_is_not_silently_priced(value):
    with pytest.raises(ValueError):
        nonnegative_decimal(value, "Rate/word")


@pytest.mark.parametrize("count", [-1, 1.2, "nan", True])
def test_word_count_must_be_a_nonnegative_integer(count):
    with pytest.raises(ValueError):
        translation_fee_eur(count, .027)


def test_future_defaults_are_shared_without_rewriting_saved_custom_rates(tmp_path):
    path = tmp_path / "settings.json"
    assert load_joblog_settings_from_path(path)["default_rate_per_word"] == dict.fromkeys(["EN", "FR", "AR"], .027)
    assert not path.exists()
    raw = json.dumps({"default_rate_per_word": {"EN": .08, "FR": "0,03", "AR": .09}, "unrelated": "retained"})
    path.write_text(raw, encoding="utf-8")
    assert load_joblog_settings_from_path(path)["default_rate_per_word"] == {"EN": .08, "FR": .03, "AR": .09}
    assert path.read_text(encoding="utf-8") == raw


def test_invalid_saved_rates_fall_back_without_writing(tmp_path):
    path = tmp_path / "settings.json"
    raw = '{"default_rate_per_word":{"EN":true,"FR":"NaN","AR":-1}}'
    path.write_text(raw, encoding="utf-8")
    assert load_joblog_settings_from_path(path)["default_rate_per_word"] == dict.fromkeys(["EN", "FR", "AR"], .027)
    assert path.read_text(encoding="utf-8") == raw


@pytest.mark.parametrize("rates", [{"EN": "NaN"}, {"AR": -.02}, {"FR": True}, {"DE": .027}, []])
def test_invalid_rate_settings_fail_before_any_write(tmp_path, rates):
    from legalpdf_translate.power_tools_service import save_browser_settings

    path = tmp_path / "settings.json"
    raw = '{"default_rate_per_word":{"EN":0.08},"unrelated":"retained"}'
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        save_browser_settings(settings_path=path, values={"default_rate_per_word": rates})
    assert path.read_text(encoding="utf-8") == raw
