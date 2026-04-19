"""Groq driver — free fallback using a Groq-hosted OSS model via the OpenAI-compatible API.

Default model is Llama 4 Scout (see `GROQ_MODEL` env var). No prompt caching
on Groq, so we use the lean system prompt (omits examples) to keep per-call token
cost down.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import openai
from openai import AsyncOpenAI

from api.config import settings
from api.drivers._prompts import SYSTEM_PROMPT_LEAN, user_message

# Groq's free tier enforces tight per-minute token limits (varies by model —
# e.g. 12k TPM for some 70B models). A single chunk rarely trips it, but a 429
# can still happen if the account recently spent tokens elsewhere. Back off and
# retry.
_MAX_RETRIES = 4
_BASE_BACKOFF_SEC = 3.0


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
        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
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
            except openai.RateLimitError as e:
                last_err = e
                wait = _retry_after_seconds(e, attempt)
                if attempt == _MAX_RETRIES - 1:
                    break
                await asyncio.sleep(wait)
        assert last_err is not None
        raise last_err


def _retry_after_seconds(err: openai.RateLimitError, attempt: int) -> float:
    """Honor Retry-After when the provider supplies it; otherwise exponential backoff."""
    header = None
    try:
        header = err.response.headers.get("retry-after")  # type: ignore[attr-defined]
    except Exception:
        pass
    if header:
        try:
            return float(header)
        except (TypeError, ValueError):
            pass
    return _BASE_BACKOFF_SEC * (2 ** attempt)


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
