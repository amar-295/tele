import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import APIStatusError, RateLimitError
from pydantic import BaseModel, Field

from ai.llm import stream_llm
from ai.memory import MemoryStore
from ai.pipeline import (
    _SYSTEM_TEMPLATE,
    _build_memory_block,
    _dispatch_background_tasks,
    _fetch_context,
    _prepare_messages,
    run_pipeline,
)
from config import settings
from storage.database import Database
from utils.llm_errors import provider_error_reply

log = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class FactRequest(BaseModel):
    fact: str = Field(..., min_length=1)


def _error_status_code(exc: BaseException) -> int:
    if isinstance(exc, RateLimitError):
        return 429
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", None)
        if isinstance(code, int):
            return code
    return 502


def _error_payload(exc: BaseException) -> dict[str, str]:
    detail = provider_error_reply(exc) or "The AI backend could not complete this request."
    return {"detail": detail}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.init()
    await MemoryStore.init()
    log.info("API ready. Model: %s", settings.groq_model)
    try:
        yield
    finally:
        await Database.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    api_key = request.headers.get("X-API-Key")
    if api_key != settings.ui_api_key:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


async def _stream_pipeline(user_message: str) -> AsyncGenerator[str, None]:
    await Database.add_message("user", user_message)
    await Database.increment_stat("messages_sent")

    all_facts, raw_history, recalled = await _fetch_context(user_message)
    memory_block = _build_memory_block(all_facts, recalled)
    system = _SYSTEM_TEMPLATE.format(
        memory_block=memory_block,
        date=datetime.now(timezone.utc).strftime("%A, %B %d, %Y"),
    )
    messages = _prepare_messages(raw_history, user_message)

    reply_parts: list[str] = []
    try:
        async for token in stream_llm(messages=messages, system=system):
            if not token:
                continue
            reply_parts.append(token)
            yield f"data: {json.dumps(token)}\n\n"
    except Exception as exc:
        detail = _error_payload(exc)["detail"]
        log.warning("Streaming chat failed: %s", exc)
        yield f"data: {json.dumps({'error': detail})}\n\n"
        yield "data: [DONE]\n\n"
        return

    reply = "".join(reply_parts)
    await Database.add_message("assistant", reply)
    await Database.increment_stat("replies_sent")
    _dispatch_background_tasks(user_message, reply)

    log.info(
        "Stream pipeline done | facts=%d | recalled=%d | history=%d msgs",
        len(all_facts),
        len(recalled),
        len(messages),
    )
    yield "data: [DONE]\n\n"


@app.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    return StreamingResponse(
        _stream_pipeline(payload.message.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat")
async def chat(payload: ChatRequest):
    try:
        reply = await run_pipeline(payload.message.strip())
    except Exception as exc:
        payload = _error_payload(exc)
        raise HTTPException(status_code=_error_status_code(exc), detail=payload["detail"]) from exc
    return {"reply": reply}


@app.get("/memory")
async def get_memory():
    return {"facts": await Database.get_all_facts()}


@app.post("/memory")
async def add_memory(payload: FactRequest):
    fact = payload.fact.strip()
    added = await Database.add_fact(fact, source="manual")
    if added:
        digest = hashlib.sha256(fact.encode("utf-8")).hexdigest()[:16]
        await MemoryStore.save(fact, f"manual_fact_{digest}", collection="facts")
    return {"added": added}


@app.delete("/memory/{keyword}")
async def delete_memory(keyword: str):
    deleted_facts, deleted_vectors = await asyncio.gather(
        Database.delete_facts_by_keyword(keyword),
        MemoryStore.delete_by_keyword(keyword),
    )
    return {"deleted": deleted_facts + deleted_vectors}


@app.get("/stats")
async def get_stats():
    vectors = await MemoryStore.count()
    messages_sent, replies_sent, message_count, fact_count = await asyncio.gather(
        Database.get_stat("messages_sent", "0"),
        Database.get_stat("replies_sent", "0"),
        Database.get_message_count(),
        Database.get_fact_count(),
    )
    return {
        "messages_sent": int(messages_sent),
        "replies_sent": int(replies_sent),
        "message_count": message_count,
        "fact_count": fact_count,
        "vector_facts": vectors["facts"],
        "vector_conversations": vectors["conversations"],
    }


@app.post("/clear")
async def clear_history():
    await Database.clear_history()
    return {"ok": True}
