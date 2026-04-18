"""Groq driver — free fallback using Llama 3.3 70B Versatile via the OpenAI-compatible API.

No prompt caching on Groq, so we use the lean system prompt (omits examples) to
keep per-call token cost down.
"""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from api.config import settings
from api.drivers._prompts import SYSTEM_PROMPT_LEAN, user_message


class GroqDriver:
    def __init__(self) -> None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY env var is not set")
        self._client = AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    async def format_chunk(
        self,
        chunk: list[dict[str, Any]],
        style: str,
    ) -> list:
        from api.formatter import FormattedCitation

        response = await self._client.chat.completions.create(
            model=settings.groq_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_LEAN},
                {"role": "user", "content": user_message(chunk, style)},
            ],
        )

        raw = response.choices[0].message.content or ""
        return _parse_response(raw, chunk)


def _parse_response(raw: str, chunk: list[dict[str, Any]]) -> list:
    from api.formatter import FormattedCitation

    try:
        payload = json.loads(raw)
        items = payload.get("citations", [])
        return [
            FormattedCitation(
                citation_id=item["citation_id"],
                formatted_text=item["formatted_text"],
                confidence=item.get("confidence", "high"),
                note=item.get("note"),
            )
            for item in items
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [
            FormattedCitation(
                citation_id=c["citation_id"],
                formatted_text=f"[NEEDS MANUAL FORMATTING] {c.get('display_text', '')}",
                confidence="needs_review",
                note="LLM returned malformed JSON",
            )
            for c in chunk
        ]
