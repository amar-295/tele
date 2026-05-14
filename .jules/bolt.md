## 2024-05-15 - PostgreSQL COUNT(*) bottleneck in vector recall
**Learning:** In `_pg_recall`, the codebase performs a `SELECT COUNT(*)` on `embedding_memory` before every pgvector search just to check if the table is empty and clamp the `LIMIT`. However, Postgres `COUNT(*)` is O(N) due to MVCC and its performance degrades as memory grows. Furthermore, `LIMIT` inherently handles `limit > count` gracefully.
**Action:** Always check if a pre-query `COUNT(*)` is strictly necessary before vector searches; rely on `LIMIT` directly when possible.
