"""
Map OpenAI-compatible SDK errors (used with Groq) to clear Telegram replies.
"""


from typing import Optional

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)

_RATE_OR_QUOTA = (
    "Groq rate or token limits were hit (requests per minute, tokens per minute, "
    "or daily quota). Wait a few minutes, check usage and limits at "
    "https://console.groq.com , or pick another model in GROQ_MODEL. "
    "Then try again."
)


def provider_error_reply(exc: BaseException) -> Optional[str]:
    """
    If ``exc`` is a known Groq / OpenAI-SDK error, return a user-facing message.
    Otherwise return None so the caller can fall back to a generic error line.
    """
    if isinstance(exc, RateLimitError):
        return _RATE_OR_QUOTA

    if isinstance(exc, AuthenticationError):
        return (
            "Groq rejected your API key (invalid or expired). "
            "Update GROQ_API_KEY in your .env and restart the bot."
        )

    if isinstance(exc, PermissionDeniedError):
        return (
            "Groq denied this request (account or model access). "
            "Open https://console.groq.com and confirm your account and model access."
        )

    if isinstance(exc, BadRequestError):
        raw = str(exc).lower()
        if "context" in raw or "too long" in raw or (
            "maximum" in raw and "token" in raw
        ):
            return (
                "This message or conversation is too large for the model’s context window. "
                "Try /clear to shorten stored history, send a shorter message, or switch "
                "to a model with a larger context in GROQ_MODEL."
            )
        if "model" in raw and (
            "not found" in raw or "does not exist" in raw or "invalid" in raw
        ):
            return (
                "The model name in GROQ_MODEL is not accepted by Groq. "
                "See https://console.groq.com/docs/models and fix your .env ."
            )
        return f"Groq rejected the request: {exc}"

    if isinstance(exc, InternalServerError):
        return (
            "Groq returned a temporary server error. "
            "Wait a minute and try again; if it persists, check https://status.groq.com ."
        )

    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return (
            "Could not reach Groq (network error or timeout). "
            "Check your internet connection, firewall, and GROQ_BASE_URL, then try again."
        )

    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", None)
        if code == 429:
            return _RATE_OR_QUOTA
        body = str(exc).strip()
        if code is not None:
            return f"Groq returned HTTP {code}. Details: {body or 'no body'}"
        return f"Groq API error: {body or type(exc).__name__}"

    return None
