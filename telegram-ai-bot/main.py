import logging
from datetime import timedelta
from urllib.parse import urlparse

from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters

from config import settings
from bot.handlers import handle_message
from bot.commands import (
    cmd_start,
    cmd_help,
    cmd_remember,
    cmd_forget,
    cmd_memory,
    cmd_clear,
    cmd_stats,
)
from bot.proactive import proactive_digest
from storage.database import Database
from ai.memory import MemoryStore
from utils.logger import setup_logger

setup_logger()
log = logging.getLogger(__name__)


def _webhook_url_and_path(public_url: str) -> tuple[str, str]:
    """
    Return (canonical_webhook_url, url_path_without_leading_slash) for PTB run_webhook.
    If the URL has no path, default path segment is ``telegram``.
    """
    raw = public_url.strip()
    p = urlparse(raw)
    if not p.scheme or not p.netloc:
        raise ValueError(
            "TELEGRAM_WEBHOOK_URL must be absolute, e.g. https://your-host.onrender.com/telegram"
        )
    path = (p.path or "").strip("/")
    if not path:
        path = "telegram"
    canonical = f"{p.scheme}://{p.netloc}/{path}"
    if p.scheme != "https":
        log.warning(
            "Webhook URL uses scheme %r; Telegram requires HTTPS in production.",
            p.scheme,
        )
    return canonical, path


async def post_init(application):
    await Database.init()
    MemoryStore.init()
    log.info("Bot ready. Owner ID: %s | Model: %s", settings.owner_chat_id, settings.groq_model)

    if settings.proactive_digest_enabled:
        jq = application.job_queue
        if jq is None:
            log.warning(
                "PROACTIVE_DIGEST_ENABLED but job_queue is unavailable — "
                'install with: pip install "python-telegram-bot[job-queue]"'
            )
        else:
            interval = timedelta(hours=settings.proactive_digest_interval_hours)
            jq.run_repeating(
                proactive_digest,
                interval=interval,
                first=timedelta(minutes=2),
                chat_id=settings.owner_chat_id,
                name="proactive_digest",
            )
            log.info(
                "Proactive digest every %s h (first run in ~2 min)",
                settings.proactive_digest_interval_hours,
            )


def main():
    app = (
        ApplicationBuilder()
        .token(settings.telegram_token)
        .post_init(post_init)
        .build()
    )

    # Hard gate — bot ONLY responds to you
    me = filters.Chat(chat_id=settings.owner_chat_id)

    app.add_handler(CommandHandler("start",    cmd_start,    filters=me))
    app.add_handler(CommandHandler("help",     cmd_help,     filters=me))
    app.add_handler(CommandHandler("remember", cmd_remember, filters=me))
    app.add_handler(CommandHandler("forget",   cmd_forget,   filters=me))
    app.add_handler(CommandHandler("memory",   cmd_memory,   filters=me))
    app.add_handler(CommandHandler("clear",    cmd_clear,    filters=me))
    app.add_handler(CommandHandler("stats",    cmd_stats,    filters=me))
    app.add_handler(MessageHandler(filters.TEXT & me, handle_message))

    if settings.telegram_webhook_url:
        canonical, url_path = _webhook_url_and_path(settings.telegram_webhook_url)
        log.info(
            "Webhook mode | listen %s:%s | path %s | public %s",
            settings.webhook_listen,
            settings.webhook_port,
            url_path,
            canonical,
        )
        app.run_webhook(
            listen=settings.webhook_listen,
            port=settings.webhook_port,
            url_path=url_path,
            webhook_url=canonical,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=settings.drop_pending_updates,
        )
    else:
        log.info("Long polling mode (set TELEGRAM_WEBHOOK_URL + TELEGRAM_WEBHOOK_SECRET for webhooks)")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
