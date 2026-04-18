"""Claude driver — used when the user provides their own Anthropic API key."""

from __future__ import annotations

import json
from typing import Any

from anthropic import AsyncAnthropic

from api.config import settings
from api.drivers._prompts import SYSTEM_PROMPT_FULL, user_message


class ClaudeDriver:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)

    async def format_chunk(
        self,
        chunk: list[dict[str, Any]],
        style: str,
    ) -> list:
        from api.formatter import FormattedCitation

        # Prompt caching: the system block is identical across every job, so marking
        # it cache-eligible means the Nth job hits cache and pays ~10% of the input cost.
        response = await self._client.messages.create(
            model=settings.claude_model,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT_FULL,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message(chunk, style)}],
        )

        raw = response.content[0].text
        return _parse_response(raw, chunk)


def _parse_response(raw: str, chunk: list[dict[str, Any]]) -> list:
    """Parse the LLM's JSON payload; on failure mark everything in the chunk needs_review."""
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
