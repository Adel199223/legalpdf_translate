"""Exact saved semantic-only model role; no settings or credential discovery."""
from __future__ import annotations

KEY = "semantic_review_model_policy"
VERSION = "dedicated_semantic_review_model_v1"
MODEL = "gpt-6-astra"
GEMINI_VERSION = "dedicated_semantic_review_model_gemini_v1"
GEMINI_MODEL = "gemini-4-neon"
_ALLOWED_POLICIES = (
    (VERSION, MODEL),
    (GEMINI_VERSION, GEMINI_MODEL),
)


def validate_policy(value):
    if (type(value) is not dict or set(value) != {"version", "model"}
            or type(value["version"]) is not str or type(value["model"]) is not str
            or (value["version"], value["model"]) not in _ALLOWED_POLICIES):
        raise ValueError("Invalid saved semantic review model policy.")
    return dict(value)


def fresh_semantic_review_model_policy(*, primary_model: str | None = None):
    """Internal fresh-run activation; never consult this during saved replay."""
    if isinstance(primary_model, str) and primary_model.strip().lower().startswith("gemini-"):
        return {"version": GEMINI_VERSION, "model": GEMINI_MODEL}
    return {"version": VERSION, "model": MODEL}


def effective_model(saved):
    return validate_policy(saved[KEY])["model"] if KEY in saved else saved["model"]


def identity_fields(saved):
    return {KEY: validate_policy(saved[KEY])} if KEY in saved else {}
