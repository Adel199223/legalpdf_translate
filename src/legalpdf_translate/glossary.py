"""Minimal file-based glossary enforcement for preferred legal phrasing."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .types import TargetLang

_ISOLATE_CONTROL_RE = re.compile(r"[\u2066-\u2069]")
_PROTECTED_TOKEN_RE = re.compile(r"(?:[\u2066\u2067\u2068])?\[\[.*?\]\](?:\u2069)?", re.DOTALL)
_VALID_TABLE_MATCHES = {"exact", "contains"}
_VALID_SOURCE_LANGS = ("AUTO", "ANY", "PT", "EN", "FR")
_VALID_GLOSSARY_TIERS = (1, 2, 3, 4, 5, 6)
_PT_AR_COURT_JUDGMENT_PRESET_NAME = "PT→AR Court/Judgment (Tiered)"
_PT_HINT_RE = re.compile(
    r"(?:\b(?:não|para|com|de|dos|das|honorários|retenção|processo|tribunal)\b|[ãõç]|\b(?:ção|ções|ões)\b)",
    re.IGNORECASE,
)
_EN_HINT_RE = re.compile(
    r"(?:\b(?:the|and|for|with|shall|court|case|fee|payment)\b)",
    re.IGNORECASE,
)
_FR_HINT_RE = re.compile(
    r"(?:\b(?:le|la|les|des|pour|avec|tribunal|affaire|contrat)\b|[éèêàùç])",
    re.IGNORECASE,
)

GlossaryMatch = Literal["exact", "contains"]
GlossarySourceLang = Literal["AUTO", "ANY", "PT", "EN", "FR"]


@dataclass(frozen=True, slots=True)
class GlossaryRule:
    target_lang: str
    match_type: str
    match: str
    replace: str
    pattern: re.Pattern[str] | None = None


GlossaryRules = tuple[GlossaryRule, ...]


@dataclass(frozen=True, slots=True)
class GlossaryEntry:
    source_text: str
    preferred_translation: str
    match_mode: GlossaryMatch
    source_lang: GlossarySourceLang = "ANY"
    tier: int = 2

    @property
    def source(self) -> str:
        return self.source_text

    @property
    def target(self) -> str:
        return self.preferred_translation

    @property
    def match(self) -> GlossaryMatch:
        return self.match_mode


_BUILTIN_GLOSSARY_V1: dict[str, object] = {
    "version": 1,
    "rules": [
        {
            "target_lang": "AR",
            "match_type": "regex",
            "match": r"صرف\s+(?:الأتعاب|الاتعاب)(?:\s+(?:المستحقة|المقررة|الواجبة))?",
            "replace": "دفع الأتعاب المستحقة",
        },
        {
            "target_lang": "AR",
            "match_type": "regex",
            "match": r"لا\s+يخضع\s+لأي\s+(?:حجز|اقتطاع|استقطاع)(?:\s*(?:من)?\s*\(?(?:IRS)\)?)?",
            "replace": "لا يخضع لأي استقطاع (IRS)",
        },
    ],
}


_DEFAULT_AR_ENTRIES: tuple[GlossaryEntry, ...] = (
    # Tier 1
    GlossaryEntry("Notificação por carta registada", "تبليغ برسالة مضمونة", "contains", "PT", 1),
    GlossaryEntry("com Prova de Receção", "مع إشعار بالاستلام", "contains", "PT", 1),
    GlossaryEntry("Assunto: Tradução", "الموضوع: ترجمة", "exact", "PT", 1),
    GlossaryEntry("Processo Comum (Tribunal Singular)", "مسطرة عادية (محكمة منفردة)", "exact", "PT", 1),
    GlossaryEntry("SENTENÇA.", "حكم", "exact", "PT", 1),
    GlossaryEntry("I – RELATÓRIO.", "أولاً – التقرير", "exact", "PT", 1),
    GlossaryEntry("II – SANEAMENTO.", "ثانياً – المسائل التمهيدية", "exact", "PT", 1),
    GlossaryEntry("III – FUNDAMENTAÇÃO.", "ثالثاً – التعليل", "exact", "PT", 1),
    GlossaryEntry("A – DE FACTO.", "أ – من حيث الوقائع", "exact", "PT", 1),
    GlossaryEntry("Factos Provados", "الوقائع الثابتة", "exact", "PT", 1),
    GlossaryEntry("Factos não Provados", "الوقائع غير الثابتة", "exact", "PT", 1),
    GlossaryEntry("B – DE DIREITO.", "ب – من حيث القانون", "exact", "PT", 1),
    GlossaryEntry("IV – CUSTAS.", "رابعاً – المصاريف القضائية", "exact", "PT", 1),
    GlossaryEntry("V – DISPOSITIVO.", "خامساً – المنطوق", "exact", "PT", 1),
    # Tier 2
    GlossaryEntry("Ministério Público", "النيابة العامة", "exact", "PT", 2),
    GlossaryEntry("deduziu acusação", "وجهت الاتهام", "contains", "PT", 2),
    GlossaryEntry("acusação", "الاتهام", "exact", "PT", 2),
    GlossaryEntry("peça acusatória", "لائحة الاتهام", "exact", "PT", 2),
    GlossaryEntry("arguido", "المتهم", "exact", "PT", 2),
    GlossaryEntry("arguida", "المتهمة", "exact", "PT", 2),
    GlossaryEntry("contestação escrita", "مذكرة دفاع كتابية", "exact", "PT", 2),
    GlossaryEntry("audiência de julgamento", "جلسة المحاكمة", "exact", "PT", 2),
    GlossaryEntry("autos", "ملف الدعوى", "exact", "PT", 2),
    GlossaryEntry("absolvição", "البراءة", "exact", "PT", 2),
    # Tier 3
    GlossaryEntry("Fica V. Exª notificado", "يُخطر سيادتكم", "contains", "PT", 3),
    GlossaryEntry("na qualidade de", "بصفتكم", "exact", "PT", 3),
    GlossaryEntry("entregar nos autos", "إيداع بملف الدعوى", "contains", "PT", 3),
    GlossaryEntry("no prazo de", "في أجل", "exact", "PT", 3),
    GlossaryEntry("a tradução da sentença", "ترجمة الحكم", "exact", "PT", 3),
    GlossaryEntry("cuja cópia se junta", "المرفقة نسخة منه", "contains", "PT", 3),
    # Tier 4
    GlossaryEntry("p. e p. pelos artigos", "المعاقب عليها بمقتضى المواد", "contains", "PT", 4),
    GlossaryEntry("alínea", "الفقرة", "exact", "PT", 4),
    GlossaryEntry("n.º", "رقم", "exact", "PT", 4),
    GlossaryEntry("doravante", "يشار إليه فيما بعد بـ", "exact", "PT", 4),
    GlossaryEntry("in dubio pro reo", "مبدأ الشك يفسر لصالح المتهم", "exact", "PT", 4),
    GlossaryEntry("presunção de inocência", "قرينة البراءة", "exact", "PT", 4),
    # Tier 5
    GlossaryEntry("crime de falsificação de documento", "جريمة تزوير مستند", "exact", "PT", 5),
    GlossaryEntry("documento falso", "مستند مزور", "exact", "PT", 5),
    GlossaryEntry("falsificação material", "تزوير مادي", "exact", "PT", 5),
    GlossaryEntry("falsificação intelectual", "تزوير معنوي", "exact", "PT", 5),
    # Tier 6
    GlossaryEntry("Sem custas.", "دون مصاريف قضائية.", "exact", "PT", 6),
    GlossaryEntry("Notifique.", "يُبلغ.", "exact", "PT", 6),
    GlossaryEntry(
        "Lida, vai proceder-se, de imediato, ao depósito da sentença",
        "بعد تلاوته، يتم فوراً إيداع الحكم",
        "contains",
        "PT",
        6,
    ),
    GlossaryEntry("Processei e revi", "حررت وراجعت", "exact", "PT", 6),
    GlossaryEntry("O Juiz de Direito", "القاضي", "exact", "PT", 6),
)

_DEFAULT_EN_ENTRIES: tuple[GlossaryEntry, ...] = (
    # Tier 1
    GlossaryEntry("Notificação por carta registada", "Notification by registered mail", "contains", "PT", 1),
    GlossaryEntry("com Prova de Receção", "with acknowledgment of receipt", "contains", "PT", 1),
    GlossaryEntry("Assunto: Tradução", "Subject: Translation", "exact", "PT", 1),
    GlossaryEntry("Processo Comum (Tribunal Singular)", "Ordinary proceedings (single-judge court)", "exact", "PT", 1),
    GlossaryEntry("SENTENÇA.", "JUDGMENT", "exact", "PT", 1),
    GlossaryEntry("I – RELATÓRIO.", "I – REPORT", "exact", "PT", 1),
    GlossaryEntry("II – SANEAMENTO.", "II – PRELIMINARY MATTERS", "exact", "PT", 1),
    GlossaryEntry("III – FUNDAMENTAÇÃO.", "III – REASONS", "exact", "PT", 1),
    GlossaryEntry("A – DE FACTO.", "A – FACTS", "exact", "PT", 1),
    GlossaryEntry("Factos Provados", "Facts established", "exact", "PT", 1),
    GlossaryEntry("Factos não Provados", "Facts not established", "exact", "PT", 1),
    GlossaryEntry("B – DE DIREITO.", "B – LAW", "exact", "PT", 1),
    GlossaryEntry("IV – CUSTAS.", "IV – COSTS", "exact", "PT", 1),
    GlossaryEntry("V – DISPOSITIVO.", "V – OPERATIVE PART", "exact", "PT", 1),
    # Tier 2
    GlossaryEntry("Ministério Público", "Public Prosecutor’s Office", "exact", "PT", 2),
    GlossaryEntry("deduziu acusação", "brought charges", "contains", "PT", 2),
    GlossaryEntry("acusação", "indictment", "exact", "PT", 2),
    GlossaryEntry("peça acusatória", "bill of indictment", "exact", "PT", 2),
    GlossaryEntry("arguido", "defendant", "exact", "PT", 2),
    GlossaryEntry("arguida", "defendant", "exact", "PT", 2),
    GlossaryEntry("contestação escrita", "written defence", "exact", "PT", 2),
    GlossaryEntry("audiência de julgamento", "trial hearing", "exact", "PT", 2),
    GlossaryEntry("autos", "case file", "exact", "PT", 2),
    GlossaryEntry("absolvição", "acquittal", "exact", "PT", 2),
    # Tier 3
    GlossaryEntry("Fica V. Exª notificado", "You are hereby notified", "contains", "PT", 3),
    GlossaryEntry("na qualidade de", "in your capacity as", "exact", "PT", 3),
    GlossaryEntry("entregar nos autos", "file with the case file", "contains", "PT", 3),
    GlossaryEntry("no prazo de", "within", "exact", "PT", 3),
    GlossaryEntry("a tradução da sentença", "the translation of the judgment", "exact", "PT", 3),
    GlossaryEntry("cuja cópia se junta", "a copy of which is attached", "contains", "PT", 3),
    # Tier 4
    GlossaryEntry("p. e p. pelos artigos", "punishable under Articles", "contains", "PT", 4),
    GlossaryEntry("alínea", "subparagraph", "exact", "PT", 4),
    GlossaryEntry("n.º", "No.", "exact", "PT", 4),
    GlossaryEntry("doravante", "hereinafter", "exact", "PT", 4),
    GlossaryEntry("in dubio pro reo", "in dubio pro reo", "exact", "PT", 4),
    GlossaryEntry("presunção de inocência", "presumption of innocence", "exact", "PT", 4),
    # Tier 5
    GlossaryEntry("crime de falsificação de documento", "offence of document forgery", "exact", "PT", 5),
    GlossaryEntry("documento falso", "forged document", "exact", "PT", 5),
    GlossaryEntry("falsificação material", "material forgery", "exact", "PT", 5),
    GlossaryEntry("falsificação intelectual", "intellectual forgery", "exact", "PT", 5),
    # Tier 6
    GlossaryEntry("Sem custas.", "No costs.", "exact", "PT", 6),
    GlossaryEntry("Notifique.", "Notify.", "exact", "PT", 6),
    GlossaryEntry(
        "Lida, vai proceder-se, de imediato, ao depósito da sentença",
        "Having been read, the judgment shall immediately be deposited",
        "contains",
        "PT",
        6,
    ),
    GlossaryEntry("Processei e revi", "Drafted and reviewed", "exact", "PT", 6),
    GlossaryEntry("O Juiz de Direito", "The Judge", "exact", "PT", 6),
)

_DEFAULT_FR_ENTRIES: tuple[GlossaryEntry, ...] = (
    # Tier 1
    GlossaryEntry("Notificação por carta registada", "Notification par lettre recommandée", "contains", "PT", 1),
    GlossaryEntry("com Prova de Receção", "avec accusé de réception", "contains", "PT", 1),
    GlossaryEntry("Assunto: Tradução", "Objet : Traduction", "exact", "PT", 1),
    GlossaryEntry("Processo Comum (Tribunal Singular)", "Procédure commune (juge unique)", "exact", "PT", 1),
    GlossaryEntry("SENTENÇA.", "JUGEMENT", "exact", "PT", 1),
    GlossaryEntry("I – RELATÓRIO.", "I – RAPPORT", "exact", "PT", 1),
    GlossaryEntry("II – SANEAMENTO.", "II – RÉGULARITÉ DE LA PROCÉDURE", "exact", "PT", 1),
    GlossaryEntry("III – FUNDAMENTAÇÃO.", "III – MOTIFS", "exact", "PT", 1),
    GlossaryEntry("A – DE FACTO.", "A – EN FAIT", "exact", "PT", 1),
    GlossaryEntry("Factos Provados", "Faits établis", "exact", "PT", 1),
    GlossaryEntry("Factos não Provados", "Faits non établis", "exact", "PT", 1),
    GlossaryEntry("B – DE DIREITO.", "B – EN DROIT", "exact", "PT", 1),
    GlossaryEntry("IV – CUSTAS.", "IV – FRAIS", "exact", "PT", 1),
    GlossaryEntry("V – DISPOSITIVO.", "V – DISPOSITIF", "exact", "PT", 1),
    # Tier 2
    GlossaryEntry("Ministério Público", "Ministère public", "exact", "PT", 2),
    GlossaryEntry("deduziu acusação", "a présenté l’acte d’accusation", "contains", "PT", 2),
    GlossaryEntry("acusação", "acte d’accusation", "exact", "PT", 2),
    GlossaryEntry("peça acusatória", "acte d’accusation", "exact", "PT", 2),
    GlossaryEntry("arguido", "prévenu", "exact", "PT", 2),
    GlossaryEntry("arguida", "prévenue", "exact", "PT", 2),
    GlossaryEntry("contestação escrita", "mémoire en défense", "exact", "PT", 2),
    GlossaryEntry("audiência de julgamento", "audience de jugement", "exact", "PT", 2),
    GlossaryEntry("autos", "dossier de la procédure", "exact", "PT", 2),
    GlossaryEntry("absolvição", "acquittement", "exact", "PT", 2),
    # Tier 3
    GlossaryEntry("Fica V. Exª notificado", "Vous êtes par la présente notifié(e)", "contains", "PT", 3),
    GlossaryEntry("na qualidade de", "en votre qualité de", "exact", "PT", 3),
    GlossaryEntry("entregar nos autos", "verser au dossier", "contains", "PT", 3),
    GlossaryEntry("no prazo de", "dans le délai de", "exact", "PT", 3),
    GlossaryEntry("a tradução da sentença", "la traduction du jugement", "exact", "PT", 3),
    GlossaryEntry("cuja cópia se junta", "dont copie est jointe", "contains", "PT", 3),
    # Tier 4
    GlossaryEntry("p. e p. pelos artigos", "prévu et puni par les articles", "contains", "PT", 4),
    GlossaryEntry("alínea", "alinéa", "exact", "PT", 4),
    GlossaryEntry("n.º", "n°", "exact", "PT", 4),
    GlossaryEntry("doravante", "ci-après", "exact", "PT", 4),
    GlossaryEntry("in dubio pro reo", "in dubio pro reo", "exact", "PT", 4),
    GlossaryEntry("presunção de inocência", "présomption d’innocence", "exact", "PT", 4),
    # Tier 5
    GlossaryEntry("crime de falsificação de documento", "infraction de falsification de document", "exact", "PT", 5),
    GlossaryEntry("documento falso", "document falsifié", "exact", "PT", 5),
    GlossaryEntry("falsificação material", "falsification matérielle", "exact", "PT", 5),
    GlossaryEntry("falsificação intelectual", "falsification intellectuelle", "exact", "PT", 5),
    # Tier 6
    GlossaryEntry("Sem custas.", "Sans dépens.", "exact", "PT", 6),
    GlossaryEntry("Notifique.", "Notifier.", "exact", "PT", 6),
    GlossaryEntry(
        "Lida, vai proceder-se, de imediato, ao depósito da sentença",
        "Lecture faite, il sera procédé immédiatement au dépôt du jugement",
        "contains",
        "PT",
        6,
    ),
    GlossaryEntry("Processei e revi", "Rédigé et relu", "exact", "PT", 6),
    GlossaryEntry("O Juiz de Direito", "Le juge", "exact", "PT", 6),
)

_DEFAULT_TIERED_PRESET_ENTRIES_BY_LANG: dict[str, tuple[GlossaryEntry, ...]] = {
    "AR": _DEFAULT_AR_ENTRIES,
    "EN": _DEFAULT_EN_ENTRIES,
    "FR": _DEFAULT_FR_ENTRIES,
}


def _lang_code(value: TargetLang | str) -> str:
    if isinstance(value, TargetLang):
        return value.value
    return str(value).strip().upper()


def supported_target_langs() -> list[str]:
    return [lang.value for lang in TargetLang]


def valid_source_langs() -> list[str]:
    return list(_VALID_SOURCE_LANGS)


def valid_glossary_tiers() -> list[int]:
    return list(_VALID_GLOSSARY_TIERS)


def coerce_source_lang(value: object, *, default: str = "ANY") -> GlossarySourceLang:
    raw = str(value or "").strip().upper()
    if raw in _VALID_SOURCE_LANGS:
        return raw  # type: ignore[return-value]
    fallback = str(default or "ANY").strip().upper()
    if fallback in _VALID_SOURCE_LANGS:
        return fallback  # type: ignore[return-value]
    return "ANY"


def coerce_glossary_tier(value: object, *, default: int = 2) -> int:
    fallback = default if default in _VALID_GLOSSARY_TIERS else 2
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        parsed = fallback
    return max(min(parsed, 6), 1)


def default_ar_entries() -> list[GlossaryEntry]:
    return list(_DEFAULT_AR_ENTRIES)


def default_en_entries() -> list[GlossaryEntry]:
    return list(_DEFAULT_EN_ENTRIES)


def default_fr_entries() -> list[GlossaryEntry]:
    return list(_DEFAULT_FR_ENTRIES)


def default_ar_seed_preset_name() -> str:
    return _PT_AR_COURT_JUDGMENT_PRESET_NAME


def _seed_dedupe_key(entry: GlossaryEntry) -> tuple[str, str, str, int]:
    return (
        coerce_source_lang(entry.source_lang, default="ANY"),
        entry.source_text.strip(),
        entry.preferred_translation.strip(),
        int(entry.tier),
    )


def default_seed_entries_for_target_lang(target_lang: TargetLang | str) -> list[GlossaryEntry]:
    return list(_DEFAULT_TIERED_PRESET_ENTRIES_BY_LANG.get(_lang_code(target_lang), ()))


def seed_missing_entries_for_target_lang(
    target_lang: TargetLang | str,
    existing_entries: list[GlossaryEntry],
) -> list[GlossaryEntry]:
    defaults = _DEFAULT_TIERED_PRESET_ENTRIES_BY_LANG.get(_lang_code(target_lang), ())
    if not defaults:
        return sorted(list(existing_entries), key=lambda entry: (int(entry.tier), entry.source_text.casefold()))
    merged: list[GlossaryEntry] = list(existing_entries)
    seen_keys = {_seed_dedupe_key(entry) for entry in merged}
    for seed_entry in defaults:
        key = _seed_dedupe_key(seed_entry)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(seed_entry)
    return sorted(merged, key=lambda entry: (int(entry.tier), entry.source_text.casefold()))


def seed_missing_ar_entries(existing_entries: list[GlossaryEntry]) -> list[GlossaryEntry]:
    return seed_missing_entries_for_target_lang("AR", existing_entries)


def _coerce_glossary_entry(raw: object) -> GlossaryEntry | None:
    source_text: str
    preferred_translation: str
    match_raw: object
    source_lang_raw: object
    tier_raw: object
    if isinstance(raw, GlossaryEntry):
        source_text = raw.source_text
        preferred_translation = raw.preferred_translation
        match_raw = raw.match_mode
        source_lang_raw = raw.source_lang
        tier_raw = raw.tier
    elif isinstance(raw, dict):
        source_text = str(raw.get("source_text", raw.get("source", "")) or "")
        preferred_translation = str(raw.get("preferred_translation", raw.get("target", "")) or "")
        match_raw = raw.get("match_mode", raw.get("match", "exact"))
        source_lang_raw = raw.get("source_lang", "ANY")
        tier_raw = raw.get("tier", 2)
    else:
        return None

    source_clean = source_text.strip()
    target_clean = preferred_translation.strip()
    if source_clean == "" or target_clean == "":
        return None
    if _ISOLATE_CONTROL_RE.search(source_clean) or _ISOLATE_CONTROL_RE.search(target_clean):
        return None

    match_mode = str(match_raw or "exact").strip().lower()
    if match_mode not in _VALID_TABLE_MATCHES:
        return None
    source_lang = coerce_source_lang(source_lang_raw, default="ANY")
    tier = coerce_glossary_tier(tier_raw, default=2)
    return GlossaryEntry(
        source_text=source_clean,
        preferred_translation=target_clean,
        match_mode=match_mode,  # type: ignore[arg-type]
        source_lang=source_lang,
        tier=tier,
    )


def normalize_glossaries(
    glossaries_by_lang: object,
    supported_langs: list[str],
) -> dict[str, list[GlossaryEntry]]:
    normalized_langs: list[str] = []
    seen_langs: set[str] = set()
    for lang in supported_langs:
        code = _lang_code(lang)
        if code == "" or code in seen_langs:
            continue
        seen_langs.add(code)
        normalized_langs.append(code)

    raw_by_lang: dict[str, object] = {}
    if isinstance(glossaries_by_lang, dict):
        for raw_lang, raw_entries in glossaries_by_lang.items():
            code = _lang_code(str(raw_lang))
            if code != "":
                raw_by_lang[code] = raw_entries

    output: dict[str, list[GlossaryEntry]] = {}
    for lang in normalized_langs:
        rows = raw_by_lang.get(lang)
        if not isinstance(rows, list):
            output[lang] = []
            continue
        normalized_rows: list[GlossaryEntry] = []
        seen_rows: set[tuple[str, str, str, str, int]] = set()
        for raw_row in rows:
            entry = _coerce_glossary_entry(raw_row)
            if entry is None:
                continue
            row_key = (
                entry.source_text,
                entry.preferred_translation,
                entry.match_mode,
                entry.source_lang,
                int(entry.tier),
            )
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            normalized_rows.append(entry)
        output[lang] = normalized_rows
    return output


def serialize_glossaries(glossaries_by_lang: dict[str, list[GlossaryEntry]]) -> dict[str, list[dict[str, object]]]:
    output: dict[str, list[dict[str, object]]] = {}
    for lang in supported_target_langs():
        rows = glossaries_by_lang.get(lang, [])
        output[lang] = [
            {
                "source_text": entry.source_text,
                "preferred_translation": entry.preferred_translation,
                "match_mode": entry.match_mode,
                "source_lang": entry.source_lang,
                "tier": int(entry.tier),
            }
            for entry in rows
        ]
    return output


def detect_source_lang_for_glossary(source_text: str) -> str:
    text = source_text.strip()
    if text == "":
        return "AUTO"
    scores = {
        "PT": len(_PT_HINT_RE.findall(text)),
        "EN": len(_EN_HINT_RE.findall(text)),
        "FR": len(_FR_HINT_RE.findall(text)),
    }
    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]
    if best_score <= 0:
        return "AUTO"
    ties = [lang for lang, score in scores.items() if score == best_score]
    if len(ties) > 1:
        return "AUTO"
    return best_lang


def filter_entries_for_source_lang(entries: list[GlossaryEntry], detected_source_lang: str) -> list[GlossaryEntry]:
    detected = coerce_source_lang(detected_source_lang, default="AUTO")
    output: list[GlossaryEntry] = []
    for entry in entries:
        entry_lang = coerce_source_lang(entry.source_lang, default="ANY")
        if entry_lang in {"ANY", "AUTO"} or entry_lang == detected:
            output.append(entry)
    return output


def normalize_enabled_tiers_by_target_lang(
    raw: object,
    supported_langs: list[str],
) -> dict[str, list[int]]:
    default_tiers = [1, 2]
    output: dict[str, list[int]] = {}
    raw_dict = raw if isinstance(raw, dict) else {}
    for lang in supported_langs:
        code = _lang_code(lang)
        raw_values = raw_dict.get(code) if isinstance(raw_dict, dict) else None
        tiers: list[int] = []
        if isinstance(raw_values, list):
            seen: set[int] = set()
            for value in raw_values:
                if isinstance(value, bool):
                    continue
                try:
                    tier = int(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    continue
                if tier not in _VALID_GLOSSARY_TIERS:
                    continue
                if tier in seen:
                    continue
                seen.add(tier)
                tiers.append(tier)
        if not tiers:
            tiers = list(default_tiers)
        output[code] = sorted(tiers)
    return output


def filter_entries_for_prompt(
    entries: list[GlossaryEntry],
    *,
    detected_source_lang: str,
    enabled_tiers: list[int],
) -> list[GlossaryEntry]:
    source_filtered = filter_entries_for_source_lang(entries, detected_source_lang)
    allowed = set(normalize_enabled_tiers_by_target_lang({"X": enabled_tiers}, ["X"]).get("X", [1, 2]))
    return [entry for entry in source_filtered if int(entry.tier) in allowed]


def sort_entries_for_prompt(entries: list[GlossaryEntry]) -> list[GlossaryEntry]:
    return sorted(
        entries,
        key=lambda entry: (int(entry.tier), -len(entry.source_text), entry.source_text.casefold()),
    )


def cap_entries_for_prompt(
    entries: list[GlossaryEntry],
    *,
    target_lang: str,
    detected_source_lang: str,
    max_entries: int = 50,
    max_chars: int = 6000,
) -> list[GlossaryEntry]:
    if max_entries <= 0 or max_chars <= 0:
        return []
    kept: list[GlossaryEntry] = []
    for entry in entries:
        if len(kept) >= max_entries:
            break
        candidate = kept + [entry]
        block = format_glossary_for_prompt(
            target_lang,
            candidate,
            detected_source_lang=detected_source_lang,
        )
        if block and len(block) > max_chars:
            break
        kept = candidate
    return kept


def format_glossary_for_prompt(
    target_lang: str,
    entries: list[GlossaryEntry],
    *,
    detected_source_lang: str = "AUTO",
) -> str:
    if not entries:
        return ""
    lang = _lang_code(target_lang)
    detected = coerce_source_lang(detected_source_lang, default="AUTO")
    lines = [
        "<<<BEGIN GLOSSARY>>>",
        f"Target language: {lang}",
        f"Detected source language: {detected}",
        "Use preferred translations exactly when source phrase matches.",
        "Do not rewrite IDs, IBANs, case numbers, addresses, dates, or names.",
    ]
    for index, entry in enumerate(entries, start=1):
        source_text = entry.source_text.replace("\r", " ").replace("\n", " ").strip()
        target_text = entry.preferred_translation.replace("\r", " ").replace("\n", " ").strip()
        lines.append(
            f"{index}. [T{int(entry.tier)}][{entry.source_lang}][{entry.match_mode}] '{source_text}' => '{target_text}'"
        )
    lines.append("<<<END GLOSSARY>>>")
    return "\n".join(lines)


def entries_from_legacy_rules(path: Path | None) -> dict[str, list[GlossaryEntry]]:
    output: dict[str, list[GlossaryEntry]] = {lang: [] for lang in supported_target_langs()}
    if path is None:
        return output
    try:
        rules = load_glossary(path)
    except Exception:
        return output

    for rule in rules:
        if rule.match_type != "literal":
            continue
        lang = _lang_code(rule.target_lang)
        if lang not in output:
            continue
        entry = GlossaryEntry(
            source_text=rule.match.strip(),
            preferred_translation=rule.replace.strip(),
            match_mode="exact",
            source_lang="ANY",
            tier=2,
        )
        if entry.source_text == "" or entry.preferred_translation == "":
            continue
        if entry not in output[lang]:
            output[lang].append(entry)
    return output


def _validate_and_build_rules(payload: object, *, source: str) -> GlossaryRules:
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid glossary at {source}: root must be an object.")

    version = payload.get("version")
    if version != 1:
        raise ValueError(f"Invalid glossary at {source}: version must be 1.")

    raw_rules = payload.get("rules")
    if not isinstance(raw_rules, list):
        raise ValueError(f"Invalid glossary at {source}: rules must be a list.")

    rules: list[GlossaryRule] = []
    for index, raw_rule in enumerate(raw_rules):
        where = f"{source} rule[{index}]"
        if not isinstance(raw_rule, dict):
            raise ValueError(f"Invalid glossary {where}: rule must be an object.")

        target_lang = str(raw_rule.get("target_lang", "")).strip().upper()
        if target_lang not in {"EN", "FR", "AR"}:
            raise ValueError(f"Invalid glossary {where}: target_lang must be EN, FR, or AR.")

        match_type = str(raw_rule.get("match_type", "")).strip().lower()
        if match_type not in {"literal", "regex"}:
            raise ValueError(f"Invalid glossary {where}: match_type must be literal or regex.")

        match = raw_rule.get("match")
        replace = raw_rule.get("replace")
        if not isinstance(match, str) or match == "":
            raise ValueError(f"Invalid glossary {where}: match must be a non-empty string.")
        if not isinstance(replace, str) or replace == "":
            raise ValueError(f"Invalid glossary {where}: replace must be a non-empty string.")
        if _ISOLATE_CONTROL_RE.search(replace):
            raise ValueError(f"Invalid glossary {where}: replace cannot contain isolate controls.")

        pattern: re.Pattern[str] | None = None
        if match_type == "regex":
            try:
                pattern = re.compile(match)
            except re.error as exc:
                raise ValueError(f"Invalid glossary {where}: bad regex pattern: {exc}") from exc

        rules.append(
            GlossaryRule(
                target_lang=target_lang,
                match_type=match_type,
                match=match,
                replace=replace,
                pattern=pattern,
            )
        )
    return tuple(rules)


def parse_glossary_payload(payload: object, *, source: str = "payload") -> GlossaryRules:
    """Validate a glossary payload object and return compiled rules."""
    return _validate_and_build_rules(payload, source=source)


def load_glossary_from_text(text: str, *, source: str = "<memory>") -> GlossaryRules:
    """Parse and validate glossary JSON text."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid glossary JSON at {source}: {exc}") from exc
    return parse_glossary_payload(payload, source=source)


def builtin_glossary_payload() -> dict[str, object]:
    """Return a mutable copy of the built-in glossary payload."""
    return deepcopy(_BUILTIN_GLOSSARY_V1)


def builtin_glossary_json(*, indent: int = 2) -> str:
    """Return the built-in glossary payload serialized as JSON text."""
    return json.dumps(builtin_glossary_payload(), ensure_ascii=False, indent=indent)


def load_glossary(path: Path | None) -> GlossaryRules:
    """Load glossary rules from file, or use built-in defaults when path is None."""
    if path is None:
        return parse_glossary_payload(builtin_glossary_payload(), source="builtin")

    glossary_path = path.expanduser().resolve()
    try:
        raw = glossary_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Unable to read glossary file: {glossary_path}") from exc

    return load_glossary_from_text(raw, source=str(glossary_path))


def _apply_rules_to_segment(text: str, *, rules: GlossaryRules) -> str:
    transformed = text
    for rule in rules:
        if rule.target_lang != "AR":
            continue
        if rule.match_type == "literal":
            transformed = transformed.replace(rule.match, rule.replace)
        else:
            assert rule.pattern is not None
            transformed = rule.pattern.sub(rule.replace, transformed)
    return transformed


def apply_glossary(text: str, target_lang: TargetLang | str, rules: GlossaryRules) -> str:
    """Apply glossary rules conservatively to AR output only."""
    if text == "":
        return text
    if _lang_code(target_lang) != "AR":
        return text
    if not rules:
        return text

    output: list[str] = []
    cursor = 0
    for token_match in _PROTECTED_TOKEN_RE.finditer(text):
        start, end = token_match.span()
        output.append(_apply_rules_to_segment(text[cursor:start], rules=rules))
        output.append(token_match.group(0))
        cursor = end
    output.append(_apply_rules_to_segment(text[cursor:], rules=rules))
    return "".join(output)
