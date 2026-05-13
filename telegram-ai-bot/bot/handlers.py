import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from ai.pipeline import run_pipeline
from utils.llm_errors import provider_error_reply

log = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_msg = (update.message.text or "").strip()
    if not user_msg:
        return

    try:
        await update.message.chat.send_action(ChatAction.TYPING)
        reply = await run_pipeline(user_msg)
        # Split if reply exceeds Telegram's 4096-char limit
        for chunk in _split(reply, 4000):
            await update.message.reply_text(chunk)
    except Exception as exc:
        log.error("handle_message error: %s", exc, exc_info=True)
        friendly = provider_error_reply(exc)
        if friendly:
            await update.message.reply_text(friendly)
        else:
            await update.message.reply_text(
                "Something unexpected went wrong. Check the bot logs for details, then try again."
            )


def _split(text: str, max_len: int) -> list[str]:
    """Split long text at paragraph breaks to stay under Telegram's limit."""
    if len(text) <= max_len:
        return [text]
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 > max_len:
            if current:
                chunks.append(current.strip())
            current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current:
        chunks.append(current.strip())
    return chunks or [text[:max_len]]
