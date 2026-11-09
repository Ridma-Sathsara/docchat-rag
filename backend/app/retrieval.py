"""Hybrid retrieval: vector similarity + keyword search, merged with Reciprocal Rank Fusion.

Vector search finds chunks that *mean* the same thing as the question; keyword
search catches exact terms (names, codes, acronyms) that embeddings often blur.
RRF combines the two ranked lists without needing their scores to be comparable.
"""

from .config import get_settings
from .db import connect
from .embeddings import embed_query

RRF_K = 60  # Standard constant from the RRF paper; dampens the weight of top ranks.

HYBRID_SQL = """
WITH vector_hits AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %(qvec)s) AS rank
    FROM chunks
    WHERE %(doc_ids)s::int[] IS NULL OR document_id = ANY(%(doc_ids)s)
    ORDER BY embedding <=> %(qvec)s
    LIMIT %(pool)s
),
keyword_hits AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS rank
    FROM chunks, websearch_to_tsquery('english', %(qtext)s) AS q
    WHERE tsv @@ q
      AND (%(doc_ids)s::int[] IS NULL OR document_id = ANY(%(doc_ids)s))
    ORDER BY ts_rank_cd(tsv, q) DESC
    LIMIT %(pool)s
),
fused AS (
    SELECT id, SUM(1.0 / (%(rrf_k)s + rank)) AS score
    FROM (SELECT * FROM vector_hits UNION ALL SELECT * FROM keyword_hits) hits
    GROUP BY id
)
SELECT c.id, c.document_id, d.filename, c.page, c.chunk_index, c.content, f.score
FROM fused f
JOIN chunks c ON c.id = f.id
JOIN documents d ON d.id = c.document_id
ORDER BY f.score DESC
LIMIT %(top_k)s
"""


def search(query: str, document_ids: list[int] | None = None, top_k: int | None = None) -> list[dict]:
    k = top_k or get_settings().top_k
    with connect() as conn:
        rows = conn.execute(
            HYBRID_SQL,
            {
                "qvec": embed_query(query),
                "qtext": query,
                "doc_ids": document_ids or None,
                "pool": k * 4,
                "rrf_k": RRF_K,
                "top_k": k,
            },
        ).fetchall()
    return [{**r, "score": float(r["score"])} for r in rows]
