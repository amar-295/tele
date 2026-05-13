"""
pipeline.py — The heart of the bot.

Every incoming message flows through:
  1. Persist user message
  2. Parallel fetch: recent history + all facts + vector recall
  3. Build system prompt injecting memory
  4. Trim history to token budget
  5. Call Groq LLM with retry
  6. Persist assistant reply
  7. Save conversation to vector store (background)
  8. Extract new facts (background)

Steps 7 & 8 are fire-and-forget asyncio tasks — they never block the reply.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict

from ai.llm import call_llm, trim_to_token_budget
from ai.memory import MemoryStore
from ai.extractor import extract_and_store
from storage.database import Database
from config import settings

log = logging.getLogger(__name__)

# ── System prompt template ─────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
You are a highly capable personal AI assistant that grows smarter about your user over time.
You learn from every conversation and remember facts about them.

━━━ What you know about your user ━━━
{memory_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Guidelines:
- Be direct, warm, and genuinely helpful.
- Naturally reference past context when relevant — don't announce that you're doing it.
- If a message relates to something you remember, use that knowledge proactively.
- Match the user's energy and communication style.
- Ask a clarifying follow-up only when it meaningfully helps.
- Today is {date}.\
"""


def _build_memory_block(facts: List[str], extra_context: List[str]) -> str:
    parts: List[str] = []

    if facts:
        bullet_facts = "\n".join(f"• {f}" for f in facts[: settings.max_facts_in_prompt])
        parts.append(f"Stored facts about you:\n{bullet_facts}")

    # Extra context = vector recall hits NOT already in facts
    facts_set = set(facts)
    novel = [c for c in extra_context if c not in facts_set][:6]
    if novel:
        bullet_ctx = "\n".join(f"• {c}" for c in novel)
        parts.append(f"Related context from past conversations:\n{bullet_ctx}")

    if not parts:
        return "No memories yet — this is the start of our history together."

    return "\n\n".join(parts)


# ── Main entry point ────────────────────────────────────────────────────────────

async def run_pipeline(user_message: str) -> str:
    """Process one user message end-to-end. Returns the assistant reply."""

    # 1. Persist user turn
    await Database.add_message("user", user_message)
    await Database.increment_stat("messages_sent")

    # 2. Parallel data fetch
    facts_task   = asyncio.create_task(Database.get_all_facts())
    history_task = asyncio.create_task(
        Database.get_recent_history(limit=settings.max_history_messages)
    )
    recall_task  = asyncio.create_task(MemoryStore.recall(user_message))

    all_facts, raw_history, recalled = await asyncio.gather(
        facts_task, history_task, recall_task
    )

    # 3. Build system prompt
    memory_block = _build_memory_block(all_facts, recalled)
    system = _SYSTEM_TEMPLATE.format(
        memory_block=memory_block,
        date=datetime.now(timezone.utc).strftime("%A, %B %d, %Y"),
    )

    # 4. Trim history to token budget
    #    The last message is the current user turn — exclude it from history.
    history: List[Dict] = raw_history
    if history and history[-1]["role"] == "user":
        history = history[:-1]
    history = trim_to_token_budget(history)

    messages = history + [{"role": "user", "content": user_message}]

    # 5. Call Groq (with built-in retry)
    reply = await call_llm(messages=messages, system=system)

    # 6. Persist assistant turn
    await Database.add_message("assistant", reply)
    await Database.increment_stat("replies_sent")

    # 7. Background: embed this exchange for future recall
    exchange = f"User: {user_message}\nAssistant: {reply}"
    doc_id   = f"conv_{int(datetime.now(timezone.utc).timestamp())}"
    asyncio.create_task(
        MemoryStore.save(exchange, doc_id, collection="conversations")
    )

    # 8. Background: extract and store new facts
    asyncio.create_task(extract_and_store(user_message, reply))

    log.info(
        "Pipeline done | facts=%d | recalled=%d | history=%d msgs",
        len(all_facts), len(recalled), len(messages),
    )
    return reply
