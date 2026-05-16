import asyncio
import logging
from typing import Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions

from config import settings
from storage.database import Database

log = logging.getLogger(__name__)

# Chroma DefaultEmbeddingFunction uses all-MiniLM-L6-v2 → 384 dims (must match DB column).
_EMBEDDING_DIM = 384


def _vector_to_pg_literal(values: List[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in values) + "]"


class MemoryStore:
    """
    Vector memory: **ChromaDB** when using SQLite only, **pgvector** (same Postgres as
    ``DATABASE_URL``) when the bot uses PostgreSQL — survives Render redeploys.
    """

    _pgvector: bool = False
    _client: Optional[chromadb.PersistentClient] = None
    _ef = None
    _facts: Optional[chromadb.Collection] = None
    _convos: Optional[chromadb.Collection] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    @classmethod
    async def init(cls) -> None:
        pool = Database.pg_pool()
        if pool is not None:
            cls._pgvector = True
            cls._client = None
            cls._facts = cls._convos = None
            loop = asyncio.get_running_loop()
            cls._ef = await loop.run_in_executor(
                None,
                lambda: embedding_functions.DefaultEmbeddingFunction(),
            )
            nf, nc = await cls._pg_counts(pool)
            log.info(
                "pgvector ready (Postgres) | facts: %d | conversations: %d",
                nf,
                nc,
            )
            return

        cls._pgvector = False
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
            cls._facts.count(),
            cls._convos.count(),
        )

    @classmethod
    async def _pg_counts(cls, pool) -> tuple[int, int]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT collection, COUNT(*)::int AS c FROM embedding_memory GROUP BY collection"
            )
        counts = {"facts": 0, "conversations": 0}
        for r in rows:
            counts[r["collection"]] = r["c"]
        return counts["facts"], counts["conversations"]

    @classmethod
    def _embed_sync(cls, texts: List[str]) -> List[List[float]]:
        raw = cls._ef(input=texts)
        out: List[List[float]] = []
        for row in raw:
            if hasattr(row, "tolist"):
                row = row.tolist()
            vec = [float(x) for x in row]
            if len(vec) != _EMBEDDING_DIM:
                raise ValueError(
                    f"Embedding dim {len(vec)} != {_EMBEDDING_DIM} (all-MiniLM-L6-v2)"
                )
            out.append(vec)
        return out

    # ── Write ──────────────────────────────────────────────────────────────

    @classmethod
    async def save(cls, text: str, doc_id: str, collection: str = "facts") -> None:
        if collection not in ("facts", "conversations"):
            collection = "facts"

        if cls._pgvector:
            pool = Database.pg_pool()
            loop = asyncio.get_running_loop()
            try:
                vecs = await loop.run_in_executor(
                    None, lambda: cls._embed_sync([text])
                )
                lit = _vector_to_pg_literal(vecs[0])
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO embedding_memory (id, collection, content, embedding)
                        VALUES ($1, $2, $3, $4::vector)
                        ON CONFLICT (id) DO UPDATE SET
                          content = EXCLUDED.content,
                          embedding = EXCLUDED.embedding,
                          created_at = timezone('utc', now())
                        """,
                        doc_id,
                        collection,
                        text,
                        lit,
                    )
                log.debug("Saved to pgvector '%s': %s …", collection, text[:60])
            except Exception as exc:
                log.error("MemoryStore.save error (%s): %s", collection, exc)
            return

        coll = cls._facts if collection == "facts" else cls._convos
        loop = asyncio.get_running_loop()
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
        if n is None:
            n = settings.memory_top_k
        threshold = settings.memory_threshold

        if cls._pgvector:
            return await cls._pg_recall(query, n, threshold)

        loop = asyncio.get_running_loop()

        # Pre-compute the embedding once instead of doing it inside each parallel query.
        # This avoids redundant embedding computations since both collections use the
        # same query text and embedding function, yielding a ~2x speedup in recall.
        q_emb = await loop.run_in_executor(None, lambda: cls._ef([query])[0])
        if hasattr(q_emb, "tolist"):
            q_emb = q_emb.tolist()

        async def _query_coll(coll: chromadb.Collection, k: int) -> List[str]:
            count = await loop.run_in_executor(None, coll.count)
            if count == 0:
                return []
            k = min(k, count)
            try:
                res = await loop.run_in_executor(
                    None,
                    lambda: coll.query(query_embeddings=[q_emb], n_results=k),
                )
                docs = res.get("documents", [[]])[0]
                dists = res.get("distances", [[]])[0]
                return [d for d, dist in zip(docs, dists) if dist < threshold]
            except Exception as exc:
                log.warning("Recall error from '%s': %s", coll.name, exc)
                return []

        half = max(n // 2, 3)
        facts_res, convos_res = await asyncio.gather(
            _query_coll(cls._facts, half),
            _query_coll(cls._convos, half),
        )
        return cls._merge_recall(facts_res, convos_res, n)

    @classmethod
    async def _pg_recall(cls, query: str, n: int, threshold: float) -> List[str]:
        pool = Database.pg_pool()
        loop = asyncio.get_running_loop()
        vecs = await loop.run_in_executor(None, lambda: cls._embed_sync([query]))
        q_lit = _vector_to_pg_literal(vecs[0])
        half = max(n // 2, 3)

        async def _q(coll: str, k: int) -> List[str]:
            async with pool.acquire() as conn:
                c_row = await conn.fetchrow(
                    "SELECT COUNT(*)::int AS c FROM embedding_memory WHERE collection = $1",
                    coll,
                )
                if not c_row or c_row["c"] == 0:
                    return []
                lim = min(k, c_row["c"])
                rows = await conn.fetch(
                    """
                    SELECT content, (embedding <=> $1::vector) AS dist
                    FROM embedding_memory
                    WHERE collection = $2
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                    """,
                    q_lit,
                    coll,
                    lim,
                )
            return [r["content"] for r in rows if float(r["dist"]) < threshold]

        facts_res, convos_res = await asyncio.gather(
            _q("facts", half),
            _q("conversations", half),
        )
        merged = cls._merge_recall(facts_res, convos_res, n)
        log.debug("Recalled %d items (pgvector) for query: %s …", len(merged), query[:40])
        return merged

    @staticmethod
    def _merge_recall(facts_res: List[str], convos_res: List[str], n: int) -> List[str]:
        seen: set = set()
        merged: List[str] = []
        for item in facts_res + convos_res:
            if item not in seen:
                seen.add(item)
                merged.append(item)
            if len(merged) >= n:
                break
        return merged

    # ── Delete ─────────────────────────────────────────────────────────────

    @classmethod
    async def delete_by_keyword(cls, keyword: str) -> int:
        if cls._pgvector:
            pool = Database.pg_pool()
            pat = f"%{keyword}%"
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "DELETE FROM embedding_memory WHERE content ILIKE $1 RETURNING id",
                    pat,
                )
            return len(rows)

        loop = asyncio.get_running_loop()
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
        if cls._pgvector:
            pool = Database.pg_pool()
            nf, nc = await cls._pg_counts(pool)
            return {"facts": nf, "conversations": nc}

        loop = asyncio.get_running_loop()
        f = await loop.run_in_executor(None, cls._facts.count)
        c = await loop.run_in_executor(None, cls._convos.count)
        return {"facts": f, "conversations": c}
