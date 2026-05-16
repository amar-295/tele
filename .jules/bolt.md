## 2024-05-18 - [Optimize ChromaDB vector queries]
**Learning:** In ChromaDB, calling `collection.query` with `query_texts` computes the embedding inside the query. Doing this multiple times in parallel for different collections with the same query text performs redundant embedding calculations.
**Action:** Pre-compute the embedding once using `cls._ef([query])[0]` and pass it to multiple `collection.query` calls as `query_embeddings`. In testing, this avoids duplicate work and provides a ~2x speedup when querying across multiple collections.
