import json
import logging
import asyncio
from typing import List

from ai.llm import call_llm
from ai.memory import MemoryStore
from storage.database import Database

log = logging.getLogger(__name__)

_SYSTEM = """You are a silent fact extractor.
Your ONLY job: read a short conversation exchange and output a JSON array of personal facts about the user.

Rules:
- Output ONLY a valid JSON array of strings. Nothing else — no markdown, no explanation.
- Each string is one self-contained fact about the USER (not the assistant).
- Facts must be explicit or strongly implied — never guess.
- Skip pleasantries, greetings, and questions with no answers.
- Maximum 5 facts per call.
- If nothing notable, return [].

Good fact examples:
  "User lives in Chennai, India"
  "User is learning Python"
  "User prefers spicy food"
  "User dislikes waking up early"
  "User is building a Telegram bot"
"""


async def extract_and_store(user_msg: str, bot_reply: str) -> None:
    """
    Non-blocking background task:
      1. Ask the LLM to extract facts from the exchange.
      2. Persist each new fact to the database and the vector store (Chroma or pgvector).
    Errors are swallowed so they never affect the main reply.
    """
    try:
        excerpt = f"User: {user_msg}\nAssistant: {bot_reply}"
        raw = await call_llm(
            messages=[{"role": "user", "content": excerpt}],
            system=_SYSTEM,
            max_tokens=256,
        )

        # Strip accidental markdown fences
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        facts: List = json.loads(cleaned)

        if not isinstance(facts, list):
            return

        async def process_fact(fact) -> bool:
            if not isinstance(fact, str) or len(fact.strip()) < 8:
                return False

            fact = fact.strip()
            is_new = await Database.add_fact(fact, source="extracted")
            if is_new:
                # Deterministic ID from content hash
                doc_id = f"fact_{abs(hash(fact)):010d}"
                await MemoryStore.save(fact, doc_id, collection="facts")
                return True
            return False

        results = await asyncio.gather(*(process_fact(fact) for fact in facts[:5]))
        new_count = sum(results)

        if new_count:
            log.info("Extractor saved %d new fact(s)", new_count)

    except json.JSONDecodeError:
        log.debug("Extractor returned non-JSON — nothing saved")
    except Exception as exc:
        log.warning("Fact extraction failed (non-critical): %s", exc)
