import logging
from datetime import datetime, timezone

from telegram.ext import ContextTypes

from config import settings
from storage.database import Database
from ai.memory import MemoryStore

log = logging.getLogger(__name__)


async def proactive_digest(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Periodic owner-only check-in: stats only (no LLM call).
    Scheduled from main when PROACTIVE_DIGEST_ENABLED=true.
    """
    chat_id = settings.owner_chat_id
    try:
        msgs_sent = await Database.get_stat("messages_sent", "0")
        replies = await Database.get_stat("replies_sent", "0")
        facts = await Database.get_all_facts()
        vec_counts = await MemoryStore.count()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        text = (
            f"Check-in ({now})\n\n"
            f"You've sent {msgs_sent} messages; I've replied {replies} times.\n"
            f"Stored facts: {len(facts)} | "
            f"Vectors — facts: {vec_counts['facts']}, "
            f"conversations: {vec_counts['conversations']}.\n\n"
            "Reply whenever you want to continue."
        )
        await context.bot.send_message(chat_id=chat_id, text=text)
    except Exception as exc:
        log.warning("proactive_digest failed: %s", exc, exc_info=True)
