from __future__ import annotations

from app.ai.base import AIResponse
from app.ai.prompts import classify_prompt, extract_fields_prompt, parse_json_response


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import Anthropic  # optional dependency

            self._client = Anthropic(api_key=self._api_key)
        return self._client

    def _message(self, system: str, user: str) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in response.content if hasattr(block, "text"))

    def classify(self, text: str, categories: list[str], context: str = "") -> AIResponse:
        system, user = classify_prompt(text, categories, context)
        raw = self._message(system, user).strip()
        return AIResponse(text=raw, raw={"category": raw})

    def extract_fields(self, text: str, schema: dict[str, str], context: str = "") -> AIResponse:
        system, user = extract_fields_prompt(text, schema, context)
        raw = self._message(system, user)
        parsed = parse_json_response(raw)
        return AIResponse(text=raw, raw=parsed)

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        raw = self._message(system or "You are a helpful office automation assistant.", prompt)
        return AIResponse(text=raw)
