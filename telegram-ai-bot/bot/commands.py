import logging
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from storage.database import Database
from ai.memory import MemoryStore

log = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Hey! I'm your personal AI — I learn from every conversation.\n\n"
        "Commands:\n"
        "  /remember <fact>  — force-save something about yourself\n"
        "  /forget <keyword> — delete memories matching a keyword\n"
        "  /memory           — list everything I know about you\n"
        "  /clear            — wipe conversation history (facts are kept)\n"
        "  /stats            — usage and memory stats\n"
        "  /help             — show this message\n\n"
        "Just chat normally and I'll learn over time. 🧠"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_remember(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await update.message.reply_text("Usage: /remember <what I should know about you>")
        return

    is_new = await Database.add_fact(text, source="manual")
    doc_id = f"manual_{abs(hash(text)):010d}"
    await MemoryStore.save(text, doc_id, collection="facts")

    if is_new:
        await update.message.reply_text(f"✅ Got it, remembered:\n_{text}_", parse_mode="Markdown")
    else:
        await update.message.reply_text("ℹ️ I already have that in memory.")


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyword = " ".join(context.args).strip()
    if not keyword:
        await update.message.reply_text("Usage: /forget <keyword>")
        return

    db_del  = await Database.delete_facts_by_keyword(keyword)
    vec_del = await MemoryStore.delete_by_keyword(keyword)
    total   = db_del + vec_del

    if total:
        await update.message.reply_text(
            f"🗑 Deleted {db_del} fact(s) from DB and {vec_del} vector(s) "
            f"matching *{keyword}*.", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"Nothing found matching '{keyword}'.")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    facts = await Database.get_all_facts()
    if not facts:
        await update.message.reply_text(
            "No facts stored yet — just keep chatting and I'll learn! 🌱"
        )
        return

    lines = [f"{i + 1}. {f}" for i, f in enumerate(facts[:40])]
    header = f"🧠 *What I know about you* ({len(facts)} facts):\n\n"
    body   = "\n".join(lines)
    if len(facts) > 40:
        body += f"\n\n_… and {len(facts) - 40} more._"
    await update.message.reply_text(header + body, parse_mode="Markdown")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await Database.clear_history()
    await update.message.reply_text(
        "🧹 Conversation history cleared.\n"
        "Your stored facts are untouched — use /forget to remove those."
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msgs_sent   = await Database.get_stat("messages_sent",  "0")
    replies     = await Database.get_stat("replies_sent",   "0")
    msg_rows    = await Database.get_message_count()
    facts       = await Database.get_all_facts()
    vec_counts  = await MemoryStore.count()

    text = (
        f"📊 *Stats*\n\n"
        f"Messages you've sent:  {msgs_sent}\n"
        f"AI replies:            {replies}\n"
        f"History rows in DB:    {msg_rows}\n"
        f"Stored facts:          {len(facts)}\n"
        f"Vector facts:          {vec_counts['facts']}\n"
        f"Vector conversations:  {vec_counts['conversations']}\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
