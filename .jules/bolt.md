## 2024-05-15 - Fast Fact Count

**Learning:** Memory consumption and unnecessary processing in stats and digest commands due to loading all facts from DB just to compute `len(facts)`.
**Action:** Always implement a specific `COUNT(*)` query method (like `get_fact_count`) in storage components instead of fetching all records into memory when only a count is needed.