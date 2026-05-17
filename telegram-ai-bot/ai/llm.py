import logging
from typing import AsyncGenerator, List, Dict

from openai import APIConnectionError, APITimeoutError, InternalServerError
from openai import AsyncOpenAI

from config import settings
from utils.retry import async_retry

log = logging.getLogger(__name__)

_client = AsyncOpenAI(
    api_key=settings.groq_api_key,
    base_url=settings.groq_base_url,
)

_RETRYABLE = (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)


@async_retry(max_attempts=4, base_delay=1.5, max_delay=32.0, exceptions=_RETRYABLE)
async def call_llm(
    messages: List[Dict],
    system: str,
    max_tokens: int = None,
) -> str:
    """
    Call Groq (OpenAI-compatible chat completions) with automatic retry
    on transient errors. Returns the assistant message text.
    """
    if max_tokens is None:
        max_tokens = settings.max_tokens

    payload = [{"role": "system", "content": system}, *messages]

    response = await _client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=max_tokens,
        messages=payload,
    )

    text = response.choices[0].message.content or ""
    usage = response.usage
    if usage:
        log.debug(
            "Groq ← %d prompt tokens | %d completion tokens",
            usage.prompt_tokens,
            usage.completion_tokens,
        )
    return text


async def stream_llm(
    messages: List[Dict],
    system: str,
    max_tokens: int = None,
) -> AsyncGenerator[str, None]:
    """Yield text tokens from Groq as they arrive."""
    if max_tokens is None:
        max_tokens = settings.max_tokens

    payload = [{"role": "system", "content": system}, *messages]
    response = await _client.chat.completions.create(
        model=settings.groq_model,
        max_tokens=max_tokens,
        messages=payload,
        stream=True,
    )

    async for chunk in response:
        yield chunk.choices[0].delta.content or ""


def trim_to_token_budget(history: List[Dict], budget: int = None) -> List[Dict]:
    """
    Drop oldest messages until the history fits within `budget` tokens.
    Rough estimate: 1 token ≈ 4 characters.
    Always keeps at least the last 2 messages (1 user + 1 assistant turn).
    """
    if budget is None:
        budget = settings.max_history_tokens

    total = 0
    kept: List[Dict] = []
    for msg in reversed(history):
        cost = len(msg["content"]) // 4
        if total + cost > budget and len(kept) >= 2:
            break
        kept.append(msg)
        total += cost

    kept.reverse()
    if len(kept) < len(history):
        log.debug(
            "History trimmed %d → %d messages to fit %d-token budget",
            len(history), len(kept), budget,
        )
    return kept
