from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

COURT_EMAIL_DOMAIN = "tribunais.org.pt"
COURT_EMAIL_CITY_ALIASES = {
    "reguengos de monsaraz": "rmonsaraz",
    "foro alentejo": "falentejo",
}

COURT_EMAIL_SOURCE_DOCUMENT_EXACT = "document_exact"
COURT_EMAIL_SOURCE_DOCUMENT_FIRST = "document_first_email"
COURT_EMAIL_SOURCE_INFERRED = "inferred_from_vocab"
COURT_EMAIL_SOURCE_MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class CourtEmailResolution:
    selected_email: str | None
    source: str
    ambiguous: bool
    ranked_candidates: tuple[str, ...]
    document_email: str | None = None
    document_source: str | None = None

    @property
    def requires_manual_confirmation(self) -> bool:
        return bool(self.selected_email) and (self.source == COURT_EMAIL_SOURCE_INFERRED or self.ambiguous)


def sanitize_court_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip("<>[](){}\"'`")
    cleaned = re.sub(r"[.,;:]+$", "", cleaned)
    if cleaned == "":
        return None
    if "@" not in cleaned or "." not in cleaned.rsplit("@", 1)[-1]:
        return None
    return cleaned


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    ascii_like = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return ascii_like.casefold()


def court_email_local_part(email: str) -> str:
    local, _, _domain = email.partition("@")
    return local.casefold()


def _court_email_domain(email: str) -> str:
    return email.partition("@")[2].casefold()


def _court_email_domain_rank(email: str) -> tuple[int, str]:
    domain = _court_email_domain(email)
    return (0 if domain == COURT_EMAIL_DOMAIN else 1, domain)


def _court_email_city_slug(case_city: str | None, case_entity: str | None) -> str | None:
    city_source = " ".join(str(case_city or "").strip().split()) or None
    if city_source is None and case_entity:
        entity_text = " ".join(str(case_entity).strip().split())
        match = re.search(r"\bde\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-]{1,40}?)(?=\n|,|$)", entity_text, re.IGNORECASE)
        if match:
            city_source = " ".join(match.group(1).strip().split())
    normalized = _normalize_for_match(city_source or "").strip()
    if normalized == "":
        return None
    if normalized in COURT_EMAIL_CITY_ALIASES:
        return COURT_EMAIL_CITY_ALIASES[normalized]
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    return compact or None


def _infer_court_email_candidates(
    *,
    case_entity: str | None,
    case_city: str | None,
) -> list[str]:
    city_slug = _court_email_city_slug(case_city, case_entity)
    if city_slug is None:
        return []

    entity_norm = _normalize_for_match(case_entity or "")
    local_parts: list[str] = []

    def _add_local(local_part: str) -> None:
        if local_part not in local_parts:
            local_parts.append(local_part)

    if "ministerio publico" in entity_norm:
        if "trabalho" in entity_norm:
            _add_local(f"{city_slug}.trabalho.ministeriopublico")
        if "familia" in entity_norm or "menores" in entity_norm:
            _add_local(f"{city_slug}.familia.ministeriopublico")
        _add_local(f"{city_slug}.ministeriopublico")
    elif any(token in entity_norm for token in ("tribunal", "juizo", "juízo")):
        _add_local(f"{city_slug}.judicial")

    return [f"{local_part}@{COURT_EMAIL_DOMAIN}" for local_part in local_parts]


def normalize_court_email_vocab(vocab_court_emails: Iterable[str]) -> list[str]:
    buckets: dict[str, list[str]] = {}
    local_order: list[str] = []
    seen_full: set[str] = set()

    for raw_email in vocab_court_emails:
        cleaned = sanitize_court_email(str(raw_email or ""))
        if cleaned is None:
            continue
        key = cleaned.casefold()
        if key in seen_full:
            continue
        seen_full.add(key)
        local = court_email_local_part(cleaned)
        if local not in buckets:
            buckets[local] = []
            local_order.append(local)
        buckets[local].append(cleaned)

    normalized: list[str] = []
    for local in local_order:
        variants = buckets[local]
        preferred = sorted(enumerate(variants), key=lambda item: (_court_email_domain_rank(item[1]), item[0]))[0][1]
        normalized.append(preferred)
        for candidate in variants:
            if candidate.casefold() != preferred.casefold():
                normalized.append(candidate)
    return normalized


def rank_court_email_suggestions(
    *,
    exact_email: str | None,
    case_entity: str | None,
    case_city: str | None,
    vocab_court_emails: list[str],
) -> list[str]:
    ranked: list[str] = []
    seen: set[str] = set()

    def _add(email: str | None) -> None:
        cleaned = sanitize_court_email(email)
        if cleaned is None:
            return
        key = cleaned.casefold()
        if key in seen:
            return
        seen.add(key)
        ranked.append(cleaned)

    curated = normalize_court_email_vocab(vocab_court_emails)
    inferred = _infer_court_email_candidates(case_entity=case_entity, case_city=case_city)
    city_slug = _court_email_city_slug(case_city, case_entity)

    _add(exact_email)

    curated_by_local: dict[str, str] = {}
    for email in curated:
        curated_by_local.setdefault(court_email_local_part(email), email)

    for inferred_email in inferred:
        _add(curated_by_local.get(court_email_local_part(inferred_email)))

    for email in inferred:
        _add(email)

    if city_slug is not None:
        city_prefix = f"{city_slug}."
        for email in curated:
            local_part = court_email_local_part(email)
            if local_part == city_slug or local_part.startswith(city_prefix):
                _add(email)

    for email in curated:
        _add(email)

    return ranked


def choose_court_email_suggestion(
    *,
    exact_email: str | None,
    case_entity: str | None,
    case_city: str | None,
    vocab_court_emails: list[str],
) -> str | None:
    ranked = rank_court_email_suggestions(
        exact_email=exact_email,
        case_entity=case_entity,
        case_city=case_city,
        vocab_court_emails=vocab_court_emails,
    )
    return ranked[0] if ranked else None


def resolve_court_email_selection(
    *,
    document_email: str | None,
    document_source: str | None,
    case_entity: str | None,
    case_city: str | None,
    vocab_court_emails: list[str],
    selected_email: str | None = None,
    selected_email_is_manual: bool = False,
) -> CourtEmailResolution:
    cleaned_document_email = sanitize_court_email(document_email)
    cleaned_selected_email = sanitize_court_email(selected_email)
    ranked = tuple(
        rank_court_email_suggestions(
            exact_email=cleaned_document_email,
            case_entity=case_entity,
            case_city=case_city,
            vocab_court_emails=vocab_court_emails,
        )
    )
    normalized_source = document_source or (
        COURT_EMAIL_SOURCE_DOCUMENT_EXACT if cleaned_document_email else COURT_EMAIL_SOURCE_INFERRED
    )

    if selected_email_is_manual and cleaned_selected_email:
        candidates = [cleaned_selected_email, *ranked]
        deduped = tuple(dict.fromkeys(candidates))
        return CourtEmailResolution(
            selected_email=cleaned_selected_email,
            source=COURT_EMAIL_SOURCE_MANUAL,
            ambiguous=False,
            ranked_candidates=deduped,
            document_email=cleaned_document_email,
            document_source=normalized_source if cleaned_document_email else None,
        )

    if cleaned_document_email:
        return CourtEmailResolution(
            selected_email=cleaned_document_email,
            source=normalized_source,
            ambiguous=False,
            ranked_candidates=ranked,
            document_email=cleaned_document_email,
            document_source=normalized_source,
        )

    selected = ranked[0] if ranked else cleaned_selected_email
    if selected is None:
        return CourtEmailResolution(
            selected_email=None,
            source="",
            ambiguous=False,
            ranked_candidates=(),
            document_email=None,
            document_source=None,
        )

    matching_variants = [
        email
        for email in normalize_court_email_vocab(vocab_court_emails)
        if court_email_local_part(email) == court_email_local_part(selected)
    ]
    ambiguous = len({_court_email_domain(email) for email in matching_variants}) > 1
    return CourtEmailResolution(
        selected_email=selected,
        source=COURT_EMAIL_SOURCE_INFERRED,
        ambiguous=ambiguous,
        ranked_candidates=ranked,
        document_email=None,
        document_source=None,
    )


def describe_court_email_resolution(resolution: CourtEmailResolution | None) -> str:
    if resolution is None or not resolution.selected_email:
        return "Court Email unresolved."
    if resolution.source == COURT_EMAIL_SOURCE_DOCUMENT_EXACT:
        return "Court Email found in the document."
    if resolution.source == COURT_EMAIL_SOURCE_DOCUMENT_FIRST:
        return "Court Email pulled from document text."
    if resolution.source == COURT_EMAIL_SOURCE_MANUAL:
        return "Court Email manually confirmed."
    if resolution.ambiguous:
        return "Court Email inferred from saved suggestions. Conflicting saved variants exist; confirm before Gmail draft."
    return "Court Email inferred from saved suggestions; confirm before Gmail draft."


def build_court_email_confirmation_warning(resolution: CourtEmailResolution | None) -> str:
    if resolution is None or not resolution.selected_email:
        return (
            "Court Email is missing.\n\n"
            "The Gmail draft was not created. Correct or confirm Court Email first."
        )
    details = [
        "Court Email was inferred from saved suggestions instead of being found in the document."
    ]
    if resolution.ambiguous:
        details.append("Conflicting saved variants exist for the same recipient local-part.")
    details.append(f"Selected recipient: {resolution.selected_email}")
    details.append("The Gmail draft was not created. Correct or confirm Court Email first.")
    return "\n\n".join(details)


def gmail_draft_block_warning(resolution: CourtEmailResolution | None) -> str | None:
    if resolution is None or not resolution.selected_email:
        return build_court_email_confirmation_warning(resolution)
    if resolution.requires_manual_confirmation:
        return build_court_email_confirmation_warning(resolution)
    return None
