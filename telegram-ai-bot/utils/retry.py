import asyncio
import functools
import logging
from typing import Tuple, Type

log = logging.getLogger(__name__)


def async_retry(
    max_attempts: int = 4,
    base_delay: float = 1.5,
    max_delay: float = 32.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator: retry an async function with exponential backoff + jitter.

    Usage:
        @async_retry(max_attempts=4, exceptions=(RateLimitError, APIConnectionError))
        async def call_api(...): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        log.error(
                            "[retry] %s — all %d attempts exhausted. Final error: %s",
                            func.__name__, max_attempts, exc,
                        )
                        raise
                    jitter = delay * 0.1  # ±10% jitter
                    sleep_for = min(delay + jitter, max_delay)
                    log.warning(
                        "[retry] %s attempt %d/%d failed (%s). Retrying in %.1fs …",
                        func.__name__, attempt, max_attempts, exc, sleep_for,
                    )
                    await asyncio.sleep(sleep_for)
                    delay = min(delay * 2, max_delay)
        return wrapper
    return decorator
