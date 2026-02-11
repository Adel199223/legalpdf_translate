from __future__ import annotations

from legalpdf_translate.metadata_autofill import apply_service_case_default_rule


def test_non_court_service_defaults_case_fields_when_not_overridden() -> None:
    case_entity, case_city = apply_service_case_default_rule(
        case_entity="",
        case_city="",
        service_entity="GNR",
        service_city="Moura",
        case_entity_user_set=False,
        case_city_user_set=False,
        non_court_service_entities=["GNR", "PSP"],
    )
    assert case_entity == "Ministério Público"
    assert case_city == "Moura"


def test_non_court_service_does_not_override_user_case_values() -> None:
    case_entity, case_city = apply_service_case_default_rule(
        case_entity="Tribunal Judicial de Beja",
        case_city="Beja",
        service_entity="PSP",
        service_city="Moura",
        case_entity_user_set=True,
        case_city_user_set=True,
        non_court_service_entities=["GNR", "PSP"],
    )
    assert case_entity == "Tribunal Judicial de Beja"
    assert case_city == "Beja"
