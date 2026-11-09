from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from .config import get_settings


@contextmanager
def connect():
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        register_vector(conn)
        yield conn


def init_db() -> None:
    dim = get_settings().embedding_dim
    # The extension must exist before register_vector can find the type.
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id          SERIAL PRIMARY KEY,
                filename    TEXT NOT NULL,
                num_pages   INT,
                num_chunks  INT NOT NULL DEFAULT 0,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id           SERIAL PRIMARY KEY,
                document_id  INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index  INT NOT NULL,
                page         INT,
                content      TEXT NOT NULL,
                embedding    vector({dim}) NOT NULL,
                -- Generated column so keyword search stays in sync with content.
                tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
            )
            """
        )
        # HNSW index: approximate nearest-neighbour search on cosine distance.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS chunks_embedding_idx "
            "ON chunks USING hnsw (embedding vector_cosine_ops)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv)")
