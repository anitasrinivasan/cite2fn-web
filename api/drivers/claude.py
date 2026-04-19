"""Claude driver — used when the user provides their own Anthropic API key.

Supports two tiers:
- "haiku" (default): claude-haiku-4-5. Works on every Anthropic API account
  including the free tier.
- "sonnet" (opt-in): claude-sonnet-4-6. Higher quality but requires a paid
  Anthropic account. When a Sonnet call fails with a tier/permission error
  we automatically retry the same request against the Haiku model so the
  user still gets a result, and we set `on_fallback` so the caller can
  surface a banner in the review UI.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import anthropic
from anthropic import AsyncAnthropic

from api.config import settings
from api.drivers._prompts import SYSTEM_PROMPT_FULL, user_message

_MAX_RETRIES = 4
_BASE_BACKOFF_SEC = 2.0

# Error messages / API-error codes that signal "your account can't use this
# model" rather than a transient failure. Anthropic's SDK raises these as
# either PermissionDeniedError (HTTP 403) or BadRequestError (HTTP 400) with
# a body mentioning the model. We only trust exact codes + a small set of
# keywords so a true 400 from something else doesn't trigger a pointless
# fallback.
_SONNET_TIER_KEYWORDS = (
    "not_found_error",
    "model_not_found",
    "permission_error",
    "does not support",
    "not available on your current plan",
    "tier",
)


class ClaudeDriver:
    def __init__(
        self,
        api_key: str,
        model_tier: str = "haiku",
        on_fallback: Callable[[], None] | None = None,
    ) -> None:
        """Initialise the driver.

        - `model_tier`: "haiku" or "sonnet". Selects which model id to call.
        - `on_fallback`: optional callback invoked (once) the first time we
          fall back from Sonnet to Haiku. Used by the pipeline to flip the
          Job's sonnet_fell_back flag.
        """
        self._client = AsyncAnthropic(api_key=api_key)
        self._tier = model_tier
        self._on_fallback = on_fallback
        self._fallback_already_fired = False

    async def format_chunk(
        self,
        chunk: list[dict[str, Any]],
        style: str,
    ) -> list:
        # Pick the model id for this request.
        model = (
            settings.claude_sonnet_model
            if self._tier == "sonnet"
            else settings.claude_model
        )

        last_err: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.messages.create(
                    model=model,
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
            except anthropic.RateLimitError as e:
                last_err = e
                if attempt == _MAX_RETRIES - 1:
                    break
                await asyncio.sleep(_BASE_BACKOFF_SEC * (2 ** attempt))
            except (
                anthropic.PermissionDeniedError,
                anthropic.NotFoundError,
                anthropic.BadRequestError,
            ) as e:
                # Tier mismatch: the key can't use Sonnet. Fall back to Haiku
                # and retry this same request once.
                if self._tier == "sonnet" and _looks_like_tier_error(e):
                    self._tier = "haiku"
                    model = settings.claude_model
                    if not self._fallback_already_fired and self._on_fallback:
                        self._fallback_already_fired = True
                        try:
                            self._on_fallback()
                        except Exception:  # never let bookkeeping raise
                            pass
                    continue  # retry immediately with Haiku on the same attempt budget
                raise

        assert last_err is not None
        raise last_err


def _looks_like_tier_error(err: Exception) -> bool:
    msg = str(err).lower()
    return any(keyword in msg for keyword in _SONNET_TIER_KEYWORDS)


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
