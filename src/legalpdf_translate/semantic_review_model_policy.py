"""Exact saved semantic-only model role; no settings or credential discovery."""
from __future__ import annotations

KEY = "semantic_review_model_policy"
VERSION = "dedicated_semantic_review_model_v1"
MODEL = "gpt-6-astra"


def validate_policy(value):
    if (type(value) is not dict or set(value) != {"version", "model"}
            or type(value["version"]) is not str or value["version"] != VERSION
            or type(value["model"]) is not str or value["model"] != MODEL):
        raise ValueError("Invalid saved semantic review model policy.")
    return dict(value)


def fresh_semantic_review_model_policy():
    """Internal fresh-run activation; never consult this during saved replay."""
    return {"version": VERSION, "model": MODEL}


def effective_model(saved):
    return validate_policy(saved[KEY])["model"] if KEY in saved else saved["model"]


def identity_fields(saved):
    return {KEY: validate_policy(saved[KEY])} if KEY in saved else {}
