"""Local LLM provider talking to an OpenAI-compatible endpoint (e.g. Ollama, vLLM, LM Studio).

Keeping air-gapped/offline capability so the office can run entirely without
sending documents to a third-party cloud API if required.
"""
from __future__ import annotations

import httpx

from app.ai.base import AIResponse
from app.ai.prompts import classify_prompt, extract_fields_prompt, parse_json_response


class LocalLLMProvider:
    name = "local"

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    def _chat(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": 0},
        }
        response = httpx.post(f"{self._base_url}/api/chat", json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")

    def classify(self, text: str, categories: list[str], context: str = "") -> AIResponse:
        system, user = classify_prompt(text, categories, context)
        raw = self._chat(system, user).strip()
        return AIResponse(text=raw, raw={"category": raw})

    def extract_fields(self, text: str, schema: dict[str, str], context: str = "") -> AIResponse:
        system, user = extract_fields_prompt(text, schema, context)
        raw = self._chat(system, user)
        parsed = parse_json_response(raw)
        return AIResponse(text=raw, raw=parsed)

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        raw = self._chat(system or "You are a helpful office automation assistant.", prompt)
        return AIResponse(text=raw)
