from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable


_SPACE_RE = re.compile(r"\s+")
_SEPARATOR_HYPHEN_RE = re.compile(r"\s+[-–]\s+|\s+[-–]|[-–]\s+")
_PARENS_SPACE_RE = re.compile(r"\(\s+|\s+\)")
_ORDINAL_VARIANT_RE = re.compile(r"\b(?P<num>\d+)\s*(?:ª|a|re|st)\b", re.IGNORECASE)
_CPR_VARIANT_RE = re.compile(r"\bc\s*/\s*pr\b", re.IGNORECASE)
_CPD_VARIANT_RE = re.compile(r"\bc\s*/\s*pd\b", re.IGNORECASE)
_PROVA_RECECAO_RE = re.compile(r"prova\s+de\s+rece[cç][aã]o", re.IGNORECASE)
_CORREIO_ELETRONICO_RE = re.compile(r"correio\s+ele[cç]tr[oó]nico", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\bemail\b", re.IGNORECASE)
_CITY_RE = r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*(?:\s+[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*){0,6}"
_SECTION_RE = r"(?P<section>\d+\s*(?:ª|a|re|st)\s*Sec\b(?:ç[aã]o)?)"


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_legal_header_text(value: str) -> str:
    cleaned = " ".join(str(value or "").replace("\xa0", " ").split()).strip()
    if cleaned == "":
        return ""
    cleaned = _strip_accents(cleaned).casefold()
    cleaned = _SEPARATOR_HYPHEN_RE.sub(" - ", cleaned)
    cleaned = _PARENS_SPACE_RE.sub("(", cleaned)
    cleaned = cleaned.replace(" )", ")")
    cleaned = _ORDINAL_VARIANT_RE.sub(lambda match: f"{match.group('num')}a", cleaned)
    cleaned = _CPR_VARIANT_RE.sub("c/pr", cleaned)
    cleaned = _CPD_VARIANT_RE.sub("c/pd", cleaned)
    cleaned = _PROVA_RECECAO_RE.sub("prova de rececao", cleaned)
    cleaned = _CORREIO_ELETRONICO_RE.sub("correio eletronico", cleaned)
    cleaned = _EMAIL_RE.sub("email", cleaned)
    cleaned = _SPACE_RE.sub(" ", cleaned)
    return cleaned.strip(" -")


def _clean_surface(value: str) -> str:
    cleaned = " ".join(str(value or "").replace("\xa0", " ").split()).strip()
    cleaned = re.sub(r"\s+([,;:])", r"\1", cleaned)
    cleaned = _SEPARATOR_HYPHEN_RE.sub(" - ", cleaned)
    return cleaned.strip()


def _digits_only(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def _ordinal_en(number: str) -> str:
    try:
        parsed = int(number)
    except (TypeError, ValueError):
        return f"{number}th"
    if 10 <= (parsed % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(parsed % 10, "th")
    return f"{parsed}{suffix}"


def _ordinal_fr(number: str) -> str:
    try:
        parsed = int(number)
    except (TypeError, ValueError):
        return number
    if parsed == 1:
        return "1re"
    return f"{parsed}e"


def _translate_section(section_text: str, lang: str) -> str:
    number = _digits_only(section_text) or section_text.strip()
    if lang == "EN":
        return f"{_ordinal_en(number)} Section"
    if lang == "FR":
        return f"{_ordinal_fr(number)} section"
    return f"القسم {number}"


def _translate_judge(number: str, lang: str) -> str:
    if lang == "EN":
        return f"Judge {number}"
    if lang == "FR":
        return f"Juge {number}"
    return f"القاضي {number}"


def _translations_for_fixed_phrase(key: str) -> dict[str, str]:
    return {
        "notification": {
            "EN": "Notification",
            "FR": "Notification",
            "AR": "إشعار",
        },
        "notification_registered": {
            "EN": "Notification by registered mail",
            "FR": "Notification par lettre recommandée",
            "AR": "تبليغ برسالة مضمونة",
        },
        "notification_registered_ack": {
            "EN": "Notification by registered mail (with acknowledgment of receipt)",
            "FR": "Notification par lettre recommandée (avec accusé de réception)",
            "AR": "تبليغ برسالة مضمونة (مع إشعار بالاستلام)",
        },
        "notification_simple_post": {
            "EN": "Notification by ordinary mail (with proof of deposit)",
            "FR": "Notification par voie postale simple (avec preuve de dépôt)",
            "AR": "تبليغ عبر البريد العادي (مع إثبات الإيداع)",
        },
        "via_email": {
            "EN": "By email",
            "FR": "Par e-mail",
            "AR": "عبر البريد الإلكتروني",
        },
        "via_email_urgent": {
            "EN": "Urgent email",
            "FR": "E-mail urgent",
            "AR": "بريد إلكتروني مستعجل",
        },
        "urgent_case": {
            "EN": "Urgent case",
            "FR": "Affaire urgente",
            "AR": "قضية مستعجلة",
        },
        "ordinary_single": {
            "EN": "Ordinary proceedings (single-judge court)",
            "FR": "Procédure commune (juge unique)",
            "AR": "مسطرة عادية (محكمة منفردة)",
        },
        "ordinary_panel": {
            "EN": "Ordinary proceedings (panel court)",
            "FR": "Procédure commune (formation collégiale)",
            "AR": "مسطرة عادية (هيئة جماعية)",
        },
        "trial_hearing": {
            "EN": "Trial hearing",
            "FR": "Audience de jugement",
            "AR": "جلسة المحاكمة",
        },
        "conciliation_attempt_date": {
            "EN": "Date of conciliation attempt",
            "FR": "Date de la tentative de conciliation",
            "AR": "تاريخ محاولة الصلح",
        },
        "illegal_foreign_detention": {
            "EN": "Detention of a foreign national in an unlawful situation",
            "FR": "Détention d'un ressortissant étranger en situation illégale",
            "AR": "احتجاز مواطن أجنبي في وضع غير قانوني",
        },
        "work_accident_conciliation": {
            "EN": "Work accident (conciliation phase)",
            "FR": "Accident du travail (phase de conciliation)",
            "AR": "حادث شغل (مرحلة الصلح)",
        },
        "public_prosecutor": {
            "EN": "Public Prosecutor’s Office",
            "FR": "Ministère public",
            "AR": "النيابة العامة",
        },
        "republic_prosecutor_office": {
            "EN": "Republic Prosecutor's Office",
            "FR": "Parquet de la République",
            "AR": "نيابة الجمهورية",
        },
    }[key]


def header_seed_rows_for_target_lang(target_lang: str) -> list[tuple[int, str, str]]:
    lang = str(target_lang or "").strip().upper()
    rows: list[tuple[int, str, str]] = []
    for seed in _HEADER_SEED_TERMS:
        translation = seed.translations_by_lang.get(lang, "").strip()
        if translation == "":
            continue
        rows.append((seed.tier, seed.canonical_pt, translation))
    return rows


def review_shortlist_terms() -> list[str]:
    return [
        "Procuradoria do Juízo Local Criminal - 1ª Sec",
        "Inquéritos de Beja",
        "Acidente de Trabalho (F. Conciliatória)",
    ]


@dataclass(frozen=True, slots=True)
class HeaderSeedTerm:
    canonical_pt: str
    translations_by_lang: dict[str, str]
    tier: int = 1


@dataclass(frozen=True, slots=True)
class MatchedHeaderPhrase:
    key: str
    source_text: str
    preferred_translation: str
    tier: int
    line_index: int
    start: int
    end: int
    metadata_case_entity: bool = False
    metadata_rank: int = 0
    case_city: str | None = None


@dataclass(frozen=True, slots=True)
class _HeaderMatcher:
    key: str
    pattern: re.Pattern[str]
    tier: int
    priority: int
    metadata_case_entity: bool
    metadata_rank: int
    render: Callable[[re.Match[str]], dict[str, str]]
    city_group: str | None = None


_HEADER_SEED_TERMS: tuple[HeaderSeedTerm, ...] = (
    HeaderSeedTerm("Notificação", _translations_for_fixed_phrase("notification"), 1),
    HeaderSeedTerm("Notificação por carta registada", _translations_for_fixed_phrase("notification_registered"), 1),
    HeaderSeedTerm("Notificação por carta registada (c/PR)", _translations_for_fixed_phrase("notification_registered_ack"), 1),
    HeaderSeedTerm("Notificação por via postal simples (c/PD)", _translations_for_fixed_phrase("notification_simple_post"), 1),
    HeaderSeedTerm("Via email", _translations_for_fixed_phrase("via_email"), 1),
    HeaderSeedTerm("Via correio eletrónico", _translations_for_fixed_phrase("via_email"), 1),
    HeaderSeedTerm("Via email urgente", _translations_for_fixed_phrase("via_email_urgent"), 1),
    HeaderSeedTerm("Processo Urgente", _translations_for_fixed_phrase("urgent_case"), 1),
    HeaderSeedTerm("Processo Comum (Tribunal Singular)", _translations_for_fixed_phrase("ordinary_single"), 1),
    HeaderSeedTerm("Processo Comum (Tribunal Coletivo)", _translations_for_fixed_phrase("ordinary_panel"), 1),
    HeaderSeedTerm("Audiência de julgamento", _translations_for_fixed_phrase("trial_hearing"), 2),
    HeaderSeedTerm("Data de Tentativa de Conciliação", _translations_for_fixed_phrase("conciliation_attempt_date"), 2),
    HeaderSeedTerm("Detenção de Cidadão Estrangeiro em Situação Ilegal", _translations_for_fixed_phrase("illegal_foreign_detention"), 2),
    HeaderSeedTerm("Acidente de Trabalho (F. Conciliatória)", _translations_for_fixed_phrase("work_accident_conciliation"), 2),
    HeaderSeedTerm("Ministério Público", _translations_for_fixed_phrase("public_prosecutor"), 2),
    HeaderSeedTerm("Procuradoria da República", _translations_for_fixed_phrase("republic_prosecutor_office"), 2),
)


def _fixed_translations(key: str) -> Callable[[re.Match[str]], dict[str, str]]:
    def _render(_match: re.Match[str]) -> dict[str, str]:
        return _translations_for_fixed_phrase(key)

    return _render


def _public_prosecution_office_render(match: re.Match[str]) -> dict[str, str]:
    city = _clean_surface(match.group("city"))
    return {
        "EN": f"Public Prosecutor's Office - Republic Prosecutor's Office of the District of {city}",
        "FR": f"Ministère public - parquet de la République du district de {city}",
        "AR": f"النيابة العامة - نيابة الجمهورية لدائرة {city}",
    }


def _judicial_court_district_render(match: re.Match[str]) -> dict[str, str]:
    city = _clean_surface(match.group("city"))
    return {
        "EN": f"Judicial Court of the District of {city}",
        "FR": f"Tribunal judiciaire du district de {city}",
        "AR": f"المحكمة القضائية لدائرة {city}",
    }


def _local_criminal_division_render(match: re.Match[str]) -> dict[str, str]:
    city = _clean_surface(match.group("city"))
    return {
        "EN": f"Local Criminal Division of {city}",
        "FR": f"Division pénale locale de {city}",
        "AR": f"الدائرة الجنائية المحلية في {city}",
    }


def _general_jurisdiction_render(match: re.Match[str]) -> dict[str, str]:
    city = _clean_surface(match.group("city"))
    return {
        "EN": f"Division of General Jurisdiction of {city}",
        "FR": f"Division de compétence générale de {city}",
        "AR": f"دائرة الاختصاص العام في {city}",
    }


def _central_civil_criminal_render(match: re.Match[str]) -> dict[str, str]:
    city = _clean_surface(match.group("city"))
    judge = _clean_surface(match.group("judge"))
    return {
        "EN": f"Central Civil and Criminal Division of {city} - {_translate_judge(judge, 'EN')}",
        "FR": f"Division centrale civile et pénale de {city} - {_translate_judge(judge, 'FR')}",
        "AR": f"الدائرة المركزية المدنية والجنائية في {city} - {_translate_judge(judge, 'AR')}",
    }


def _labour_prosecution_render(match: re.Match[str]) -> dict[str, str]:
    city = _clean_surface(match.group("city"))
    return {
        "EN": f"Prosecution Office of the Labour Division of {city}",
        "FR": f"Parquet de la division du travail de {city}",
        "AR": f"نيابة دائرة العمل في {city}",
    }


def _local_criminal_prosecution_render(match: re.Match[str]) -> dict[str, str]:
    section = _clean_surface(match.group("section"))
    return {
        "EN": f"Prosecution Office of the Local Criminal Division - {_translate_section(section, 'EN')}",
        "FR": f"Parquet de la division pénale locale - {_translate_section(section, 'FR')}",
        "AR": f"نيابة الدائرة الجنائية المحلية - {_translate_section(section, 'AR')}",
    }


def _investigations_render(match: re.Match[str]) -> dict[str, str]:
    city = _clean_surface(match.group("city"))
    return {
        "EN": f"Investigations Unit of {city}",
        "FR": f"Service des enquêtes de {city}",
        "AR": f"وحدة التحقيقات في {city}",
    }


_HEADER_MATCHERS: tuple[_HeaderMatcher, ...] = (
    _HeaderMatcher(
        key="public_prosecutor_republic_district",
        pattern=re.compile(
            rf"Minist[ée]rio\s+P[úu]blico\s*-\s*Procuradoria\s+da\s+Rep[úu]blica\s+da\s+Comarca\s+de\s+(?P<city>{_CITY_RE})",
            re.IGNORECASE,
        ),
        tier=1,
        priority=100,
        metadata_case_entity=True,
        metadata_rank=80,
        render=_public_prosecution_office_render,
        city_group="city",
    ),
    _HeaderMatcher(
        key="labour_prosecution_office",
        pattern=re.compile(
            rf"Procuradoria\s+do\s+Ju[ií]zo\s+do\s+Trabalho\s+de\s+(?P<city>{_CITY_RE})",
            re.IGNORECASE,
        ),
        tier=1,
        priority=95,
        metadata_case_entity=True,
        metadata_rank=98,
        render=_labour_prosecution_render,
        city_group="city",
    ),
    _HeaderMatcher(
        key="local_criminal_prosecution_section",
        pattern=re.compile(
            rf"Procuradoria\s+do\s+Ju[ií]zo\s+Local\s+Criminal\s*-\s*{_SECTION_RE}",
            re.IGNORECASE,
        ),
        tier=1,
        priority=94,
        metadata_case_entity=True,
        metadata_rank=99,
        render=_local_criminal_prosecution_render,
    ),
    _HeaderMatcher(
        key="judicial_court_district",
        pattern=re.compile(
            rf"Tribunal\s+Judicial\s+da\s+Comarca\s+de\s+(?P<city>{_CITY_RE})",
            re.IGNORECASE,
        ),
        tier=1,
        priority=90,
        metadata_case_entity=True,
        metadata_rank=70,
        render=_judicial_court_district_render,
        city_group="city",
    ),
    _HeaderMatcher(
        key="local_criminal_division",
        pattern=re.compile(
            rf"Ju[ií]zo\s+Local\s+Criminal\s+de\s+(?P<city>{_CITY_RE})",
            re.IGNORECASE,
        ),
        tier=1,
        priority=89,
        metadata_case_entity=True,
        metadata_rank=92,
        render=_local_criminal_division_render,
        city_group="city",
    ),
    _HeaderMatcher(
        key="general_jurisdiction_division",
        pattern=re.compile(
            rf"Ju[ií]zo\s+de\s+Compet[êe]ncia\s+Gen[ée]rica\s+de\s+(?P<city>{_CITY_RE})",
            re.IGNORECASE,
        ),
        tier=1,
        priority=88,
        metadata_case_entity=True,
        metadata_rank=91,
        render=_general_jurisdiction_render,
        city_group="city",
    ),
    _HeaderMatcher(
        key="central_civil_criminal_division",
        pattern=re.compile(
            rf"Ju[ií]zo\s+Central\s+C[ií]vel\s+e\s+Criminal\s+de\s+(?P<city>{_CITY_RE})\s*-\s*Juiz\s+(?P<judge>\d+)",
            re.IGNORECASE,
        ),
        tier=1,
        priority=87,
        metadata_case_entity=True,
        metadata_rank=93,
        render=_central_civil_criminal_render,
        city_group="city",
    ),
    _HeaderMatcher(
        key="investigations_unit",
        pattern=re.compile(
            rf"Inqu[ée]ritos\s+de\s+(?P<city>{_CITY_RE})",
            re.IGNORECASE,
        ),
        tier=1,
        priority=86,
        metadata_case_entity=True,
        metadata_rank=85,
        render=_investigations_render,
        city_group="city",
    ),
    _HeaderMatcher(
        key="notification_registered_ack",
        pattern=re.compile(
            r"Notifica(?:ç|c)[aã]o\s+por\s+carta\s+registada(?:\s*(?:\(\s*c\s*/\s*PR\s*\)|com\s+Prova\s+de\s+Rece(?:ç|c)[aã]o))",
            re.IGNORECASE,
        ),
        tier=1,
        priority=80,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("notification_registered_ack"),
    ),
    _HeaderMatcher(
        key="notification_simple_post",
        pattern=re.compile(
            r"Notifica(?:ç|c)[aã]o\s+por\s+via\s+postal\s+simples\s*(?:\(\s*c\s*/\s*PD\s*\))",
            re.IGNORECASE,
        ),
        tier=1,
        priority=79,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("notification_simple_post"),
    ),
    _HeaderMatcher(
        key="notification_registered",
        pattern=re.compile(
            r"Notifica(?:ç|c)[aã]o\s+por\s+carta\s+registada",
            re.IGNORECASE,
        ),
        tier=1,
        priority=78,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("notification_registered"),
    ),
    _HeaderMatcher(
        key="notification",
        pattern=re.compile(r"\bNotifica(?:ç|c)[aã]o\b", re.IGNORECASE),
        tier=1,
        priority=77,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("notification"),
    ),
    _HeaderMatcher(
        key="via_email_urgent",
        pattern=re.compile(r"Via\s+email\s+urgente", re.IGNORECASE),
        tier=1,
        priority=76,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("via_email_urgent"),
    ),
    _HeaderMatcher(
        key="via_email",
        pattern=re.compile(r"Via\s+email", re.IGNORECASE),
        tier=1,
        priority=75,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("via_email"),
    ),
    _HeaderMatcher(
        key="via_correio_eletronico",
        pattern=re.compile(r"Via\s+correio\s+ele[cç]tr[oó]nico", re.IGNORECASE),
        tier=1,
        priority=74,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("via_email"),
    ),
    _HeaderMatcher(
        key="urgent_case",
        pattern=re.compile(r"Processo\s+Urgente", re.IGNORECASE),
        tier=1,
        priority=73,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("urgent_case"),
    ),
    _HeaderMatcher(
        key="ordinary_panel",
        pattern=re.compile(r"Processo\s+Comum\s*\(\s*Tribunal\s+Coletivo\s*\)", re.IGNORECASE),
        tier=1,
        priority=72,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("ordinary_panel"),
    ),
    _HeaderMatcher(
        key="ordinary_single",
        pattern=re.compile(r"Processo\s+Comum\s*\(\s*Tribunal\s+Singular\s*\)", re.IGNORECASE),
        tier=1,
        priority=71,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("ordinary_single"),
    ),
    _HeaderMatcher(
        key="trial_hearing",
        pattern=re.compile(r"Audi[êe]ncia\s+de\s+julgamento", re.IGNORECASE),
        tier=2,
        priority=70,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("trial_hearing"),
    ),
    _HeaderMatcher(
        key="conciliation_attempt_date",
        pattern=re.compile(r"Data\s+de\s+Tentativa\s+de\s+Concilia(?:ç|c)[aã]o", re.IGNORECASE),
        tier=2,
        priority=69,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("conciliation_attempt_date"),
    ),
    _HeaderMatcher(
        key="illegal_foreign_detention",
        pattern=re.compile(r"Deten(?:ç|c)[aã]o\s+de\s+Cidad[aã]o\s+Estrangeiro\s+em\s+Situa(?:ç|c)[aã]o\s+Ilegal", re.IGNORECASE),
        tier=2,
        priority=68,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("illegal_foreign_detention"),
    ),
    _HeaderMatcher(
        key="work_accident_conciliation",
        pattern=re.compile(r"Acidente\s+de\s+Trabalho\s*\(\s*F\.\s*Conciliat[oó]ria\s*\)", re.IGNORECASE),
        tier=2,
        priority=67,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("work_accident_conciliation"),
    ),
    _HeaderMatcher(
        key="public_prosecutor",
        pattern=re.compile(r"Minist[ée]rio\s+P[úu]blico", re.IGNORECASE),
        tier=2,
        priority=66,
        metadata_case_entity=True,
        metadata_rank=75,
        render=_fixed_translations("public_prosecutor"),
    ),
    _HeaderMatcher(
        key="republic_prosecutor_office",
        pattern=re.compile(r"Procuradoria\s+da\s+Rep[úu]blica", re.IGNORECASE),
        tier=2,
        priority=65,
        metadata_case_entity=False,
        metadata_rank=0,
        render=_fixed_translations("republic_prosecutor_office"),
    ),
)


def match_legal_header_phrases(source_text: str, target_lang: str) -> list[MatchedHeaderPhrase]:
    lang = str(target_lang or "").strip().upper()
    if lang == "":
        return []
    matches: list[MatchedHeaderPhrase] = []
    seen: set[tuple[str, str]] = set()
    for line_index, raw_line in enumerate(str(source_text or "").splitlines()):
        line = raw_line.strip()
        if line == "":
            continue
        accepted_spans: list[tuple[int, int]] = []
        for matcher in _HEADER_MATCHERS:
            for match in matcher.pattern.finditer(line):
                start, end = match.span()
                if any(not (end <= prev_start or start >= prev_end) for prev_start, prev_end in accepted_spans):
                    continue
                translations = matcher.render(match)
                translation = str(translations.get(lang, "") or "").strip()
                if translation == "":
                    continue
                surface = _clean_surface(match.group(0))
                key = (matcher.key, normalize_legal_header_text(surface))
                if key in seen:
                    continue
                seen.add(key)
                accepted_spans.append((start, end))
                city = _clean_surface(match.group(matcher.city_group)) if matcher.city_group else None
                matches.append(
                    MatchedHeaderPhrase(
                        key=matcher.key,
                        source_text=surface,
                        preferred_translation=translation,
                        tier=matcher.tier,
                        line_index=line_index,
                        start=start,
                        end=end,
                        metadata_case_entity=matcher.metadata_case_entity,
                        metadata_rank=matcher.metadata_rank,
                        case_city=city,
                    )
                )
    return matches


def extract_best_case_entity_match(header_text: str) -> MatchedHeaderPhrase | None:
    candidates = [match for match in match_legal_header_phrases(header_text, "EN") if match.metadata_case_entity]
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item.metadata_rank,
            len(item.source_text),
            -item.line_index,
            -item.start,
        ),
        reverse=True,
    )
    return candidates[0]
