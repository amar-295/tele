import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions
from config import settings

log = logging.getLogger(__name__)


class MemoryStore:
    """
    Two-collection ChromaDB store:
      • 'facts'         — discrete personal facts extracted from chat
      • 'conversations' — full exchange embeddings for contextual recall

    All heavy I/O runs in a thread-pool executor to stay non-blocking.
    """

    _client: Optional[chromadb.PersistentClient] = None
    _ef = None
    _facts: Optional[chromadb.Collection] = None
    _convos: Optional[chromadb.Collection] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    @classmethod
    def init(cls) -> None:
        cls._client = chromadb.PersistentClient(path=settings.chroma_path)
        cls._ef = embedding_functions.DefaultEmbeddingFunction()

        cls._facts = cls._client.get_or_create_collection(
            name="facts",
            embedding_function=cls._ef,
            metadata={"hnsw:space": "cosine"},
        )
        cls._convos = cls._client.get_or_create_collection(
            name="conversations",
            embedding_function=cls._ef,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(
            "ChromaDB ready | facts: %d | conversations: %d",
            cls._facts.count(), cls._convos.count(),
        )

    # ── Write ──────────────────────────────────────────────────────────────

    @classmethod
    async def save(cls, text: str, doc_id: str, collection: str = "facts") -> None:
        coll = cls._facts if collection == "facts" else cls._convos
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: coll.upsert(documents=[text], ids=[doc_id]),
            )
            log.debug("Saved to '%s': %s …", collection, text[:60])
        except Exception as exc:
            log.error("MemoryStore.save error (%s): %s", collection, exc)

    # ── Read ───────────────────────────────────────────────────────────────

    @classmethod
    async def recall(cls, query: str, n: int = None) -> List[str]:
        """
        Query both collections. Merge, deduplicate, and filter by cosine
        distance threshold. Returns at most `n` results ranked by relevance.
        """
        if n is None:
            n = settings.memory_top_k
        threshold = settings.memory_threshold
        loop = asyncio.get_event_loop()

        async def _query_coll(coll: chromadb.Collection, k: int) -> List[str]:
            count = await loop.run_in_executor(None, coll.count)
            if count == 0:
                return []
            k = min(k, count)
            try:
                res = await loop.run_in_executor(
                    None,
                    lambda: coll.query(query_texts=[query], n_results=k),
                )
                docs  = res.get("documents", [[]])[0]
                dists = res.get("distances",  [[]])[0]
                return [d for d, dist in zip(docs, dists) if dist < threshold]
            except Exception as exc:
                log.warning("Recall error from '%s': %s", coll.name, exc)
                return []

        half = max(n // 2, 3)
        facts_res, convos_res = await asyncio.gather(
            _query_coll(cls._facts, half),
            _query_coll(cls._convos, half),
        )

        # Merge: facts first (higher signal), then conversation context
        seen: set = set()
        merged: List[str] = []
        for item in facts_res + convos_res:
            if item not in seen:
                seen.add(item)
                merged.append(item)
            if len(merged) >= n:
                break

        log.debug("Recalled %d items for query: %s …", len(merged), query[:40])
        return merged

    # ── Delete ─────────────────────────────────────────────────────────────

    @classmethod
    async def delete_by_keyword(cls, keyword: str) -> int:
        loop = asyncio.get_event_loop()
        deleted = 0
        kw_lower = keyword.lower()
        for coll in (cls._facts, cls._convos):
            try:
                all_data = await loop.run_in_executor(None, coll.get)
                ids_to_del = [
                    doc_id
                    for doc_id, doc in zip(all_data["ids"], all_data["documents"])
                    if kw_lower in doc.lower()
                ]
                if ids_to_del:
                    await loop.run_in_executor(
                        None, lambda ids=ids_to_del: coll.delete(ids=ids)
                    )
                    deleted += len(ids_to_del)
            except Exception as exc:
                log.error("delete_by_keyword error (%s): %s", coll.name, exc)
        return deleted

    # ── Stats ──────────────────────────────────────────────────────────────

    @classmethod
    async def count(cls) -> Dict[str, int]:
        loop = asyncio.get_event_loop()
        f = await loop.run_in_executor(None, cls._facts.count)
        c = await loop.run_in_executor(None, cls._convos.count)
        return {"facts": f, "conversations": c}
