"""Turn an uploaded file into page-tagged chunks and store them with embeddings."""

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader

from .config import get_settings
from .db import connect
from .embeddings import embed_documents

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


@dataclass
class Chunk:
    page: int | None
    content: str


def extract_pages(filename: str, data: bytes) -> list[tuple[int | None, str]]:
    """Return (page_number, text) pairs. Plain-text files are a single page-less unit."""
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    return [(None, data.decode("utf-8", errors="replace"))]


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Recursive-style splitter: prefer paragraph, then sentence, then word boundaries.

    Each chunk is at most `size` characters and starts `overlap` characters before
    the previous one ended, so a fact that straddles a boundary appears whole in
    at least one chunk.
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            # Look for the best natural break in the back half of the window.
            for sep in ("\n\n", "\n", ". ", " "):
                cut = window.rfind(sep, size // 2)
                if cut != -1:
                    end = start + cut + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def chunk_document(pages: list[tuple[int | None, str]]) -> list[Chunk]:
    s = get_settings()
    # Chunk per page so every chunk can cite a page number.
    return [
        Chunk(page=page, content=piece)
        for page, text in pages
        for piece in split_text(text, s.chunk_size, s.chunk_overlap)
    ]


def ingest(filename: str, data: bytes) -> dict:
    pages = extract_pages(filename, data)
    chunks = chunk_document(pages)
    if not chunks:
        raise ValueError(
            "No text could be extracted. Scanned PDFs need OCR before they can be indexed."
        )

    vectors = embed_documents([c.content for c in chunks])
    num_pages = len(pages) if filename.lower().endswith(".pdf") else None

    with connect() as conn:
        doc = conn.execute(
            "INSERT INTO documents (filename, num_pages, num_chunks) VALUES (%s, %s, %s) "
            "RETURNING id, filename, num_pages, num_chunks, created_at",
            (filename, num_pages, len(chunks)),
        ).fetchone()
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (document_id, chunk_index, page, content, embedding) "
                "VALUES (%s, %s, %s, %s, %s)",
                [
                    (doc["id"], i, c.page, c.content, v)
                    for i, (c, v) in enumerate(zip(chunks, vectors))
                ],
            )
    return doc
