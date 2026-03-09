"""Shared user-profile model for honorarios identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence
from uuid import uuid4

DEFAULT_PROFILE_IVA_TEXT = "23%"
DEFAULT_PROFILE_IRS_TEXT = "Sem retenção"
LEGACY_DEFAULT_FIRST_NAME = "Adel"
LEGACY_DEFAULT_LAST_NAME = "Belghali"
LEGACY_DEFAULT_DOCUMENT_NAME = "Adel Belghali"
LEGACY_DEFAULT_POSTAL_ADDRESS = "Rua Luís de Camões nº 6, 7960-011 Marmelar, Pedrógão, Vidigueira"
LEGACY_DEFAULT_IBAN = "PT50003506490000832760029"
DEFAULT_PRIMARY_PROFILE_ID = "primary"
PROFILE_REQUIRED_FIELDS = (
    "first_name",
    "last_name",
    "postal_address",
    "iban",
    "iva_text",
    "irs_text",
)
PROFILE_FIELD_LABELS = {
    "first_name": "First name",
    "last_name": "Last name",
    "postal_address": "Postal address",
    "iban": "IBAN",
    "iva_text": "IVA text",
    "irs_text": "IRS text",
}


def _clean(value: object) -> str:
    return str(value or "").strip()


def create_profile_id() -> str:
    return f"profile_{uuid4().hex[:12]}"


@dataclass(slots=True)
class UserProfile:
    id: str
    first_name: str
    last_name: str
    document_name_override: str = ""
    email: str = ""
    phone_number: str = ""
    postal_address: str = ""
    iban: str = ""
    iva_text: str = DEFAULT_PROFILE_IVA_TEXT
    irs_text: str = DEFAULT_PROFILE_IRS_TEXT

    @property
    def document_name(self) -> str:
        override = self.document_name_override.strip()
        if override:
            return override
        combined = " ".join(part for part in (self.first_name.strip(), self.last_name.strip()) if part)
        return combined.strip()


def default_primary_profile(*, email: str = "") -> UserProfile:
    return UserProfile(
        id=DEFAULT_PRIMARY_PROFILE_ID,
        first_name=LEGACY_DEFAULT_FIRST_NAME,
        last_name=LEGACY_DEFAULT_LAST_NAME,
        document_name_override=LEGACY_DEFAULT_DOCUMENT_NAME,
        email=_clean(email),
        phone_number="",
        postal_address=LEGACY_DEFAULT_POSTAL_ADDRESS,
        iban=LEGACY_DEFAULT_IBAN,
        iva_text=DEFAULT_PROFILE_IVA_TEXT,
        irs_text=DEFAULT_PROFILE_IRS_TEXT,
    )


def blank_profile(*, profile_id: str | None = None) -> UserProfile:
    return UserProfile(
        id=profile_id or create_profile_id(),
        first_name="",
        last_name="",
        document_name_override="",
        email="",
        phone_number="",
        postal_address="",
        iban="",
        iva_text=DEFAULT_PROFILE_IVA_TEXT,
        irs_text=DEFAULT_PROFILE_IRS_TEXT,
    )


def profile_from_mapping(value: Mapping[str, Any], *, fallback_id: str | None = None) -> UserProfile:
    profile_id = _clean(value.get("id")) or fallback_id or create_profile_id()
    return UserProfile(
        id=profile_id,
        first_name=_clean(value.get("first_name")),
        last_name=_clean(value.get("last_name")),
        document_name_override=_clean(value.get("document_name_override")),
        email=_clean(value.get("email")),
        phone_number=_clean(value.get("phone_number")),
        postal_address=_clean(value.get("postal_address")),
        iban=_clean(value.get("iban")),
        iva_text=_clean(value.get("iva_text")) or DEFAULT_PROFILE_IVA_TEXT,
        irs_text=_clean(value.get("irs_text")) or DEFAULT_PROFILE_IRS_TEXT,
    )


def serialize_profile(profile: UserProfile) -> dict[str, str]:
    payload = asdict(profile)
    return {
        key: _clean(value)
        for key, value in payload.items()
    }


def serialize_profiles(profiles: Sequence[UserProfile]) -> list[dict[str, str]]:
    return [serialize_profile(profile) for profile in profiles]


def normalize_profiles(
    raw_profiles: object,
    raw_primary_profile_id: object,
    *,
    fallback_email: str = "",
) -> tuple[list[UserProfile], str]:
    profiles: list[UserProfile] = []
    seen_ids: set[str] = set()
    if isinstance(raw_profiles, list):
        for item in raw_profiles:
            if not isinstance(item, Mapping):
                continue
            profile = profile_from_mapping(item)
            if profile.id in seen_ids:
                profile = profile_from_mapping(item, fallback_id=create_profile_id())
            seen_ids.add(profile.id)
            profiles.append(profile)
    if not profiles:
        profiles = [default_primary_profile(email=fallback_email)]
    primary_profile_id = _clean(raw_primary_profile_id)
    if not primary_profile_id or all(profile.id != primary_profile_id for profile in profiles):
        primary_profile_id = profiles[0].id
    return profiles, primary_profile_id


def primary_profile(profiles: Sequence[UserProfile], primary_profile_id: str) -> UserProfile:
    for profile in profiles:
        if profile.id == primary_profile_id:
            return profile
    if profiles:
        return profiles[0]
    return default_primary_profile()


def find_profile(profiles: Sequence[UserProfile], profile_id: str) -> UserProfile | None:
    for profile in profiles:
        if profile.id == profile_id:
            return profile
    return None


def missing_required_profile_fields(profile: UserProfile) -> tuple[str, ...]:
    missing: list[str] = []
    for field_name in PROFILE_REQUIRED_FIELDS:
        value = getattr(profile, field_name, "")
        if not _clean(value):
            missing.append(field_name)
    return tuple(missing)
