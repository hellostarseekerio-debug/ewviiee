from __future__ import annotations

from app.ai.base import AIResponse
from app.ai.prompts import classify_prompt, extract_fields_prompt, parse_json_response


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # imported lazily so it's an optional dependency

            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def _chat(self, system: str, user: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
        )
        return response.choices[0].message.content or ""

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
