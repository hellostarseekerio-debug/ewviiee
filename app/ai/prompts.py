"""Shared prompt templates for all AI providers."""
from __future__ import annotations

import json


def classify_prompt(text: str, categories: list[str], context: str = "") -> tuple[str, str]:
    system = (
        "You are a document classification assistant for a Hong Kong Legislative "
        "Council office. Respond with ONLY the single best matching category name, "
        "nothing else."
    )
    user = (
        f"{context}\n\nCategories: {', '.join(categories)}\n\n"
        f"Document text:\n{text[:4000]}\n\nBest category:"
    )
    return system, user


def extract_fields_prompt(text: str, schema: dict[str, str], context: str = "") -> tuple[str, str]:
    system = (
        "You are a structured data extraction assistant for a Hong Kong Legislative "
        "Council office. Respond with ONLY a JSON object matching the requested keys. "
        "Use null for any field you cannot find. Do not include commentary."
    )
    fields_desc = "\n".join(f"- {k}: {v}" for k, v in schema.items())
    user = (
        f"{context}\n\nExtract these fields:\n{fields_desc}\n\n"
        f"Document text:\n{text[:6000]}\n\nJSON:"
    )
    return system, user


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {}
