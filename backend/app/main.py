import json
import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import ingest, llm, retrieval
from .config import get_settings
from .db import connect, init_db

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
logger = logging.getLogger("docchat")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="DocChat RAG API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/documents")
def list_documents():
    with connect() as conn:
        return conn.execute(
            "SELECT id, filename, num_pages, num_chunks, created_at FROM documents ORDER BY created_at DESC"
        ).fetchall()


@app.post("/documents", status_code=201)
async def upload_document(file: UploadFile):
    name = Path(file.filename or "upload").name
    if Path(name).suffix.lower() not in ingest.SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Use: {', '.join(sorted(ingest.SUPPORTED_EXTENSIONS))}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    try:
        return ingest.ingest(name, data)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int):
    with connect() as conn:
        if conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,)).rowcount == 0:
            raise HTTPException(404, "Document not found")


class SearchRequest(BaseModel):
    query: str
    document_ids: list[int] | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)


@app.post("/search")
def search(req: SearchRequest):
    """Retrieval only, no LLM. Handy for debugging what the model will see."""
    return retrieval.search(req.query, req.document_ids, req.top_k)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[Turn] = []
    document_ids: list[int] | None = None


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.post("/chat")
def chat(req: ChatRequest):
    sources = retrieval.search(req.question, req.document_ids)

    def events() -> Iterator[str]:
        # Send sources first so the UI can render citation chips while the answer streams.
        yield sse("sources", [
            {"n": i, "filename": s["filename"], "page": s["page"], "content": s["content"], "score": s["score"]}
            for i, s in enumerate(sources, start=1)
        ])
        try:
            history = [t.model_dump() for t in req.history[-10:]]
            for delta in llm.stream_answer(req.question, sources, history):
                yield sse("delta", delta)
        except llm.MissingAPIKey as e:
            yield sse("error", str(e))
        except anthropic.AuthenticationError:
            yield sse("error", "Anthropic API key is missing or invalid. Set ANTHROPIC_API_KEY in backend/.env.")
        except anthropic.RateLimitError:
            yield sse("error", "Rate limited by the Anthropic API. Wait a moment and try again.")
        except anthropic.APIStatusError as e:
            yield sse("error", f"Anthropic API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            yield sse("error", "Could not reach the Anthropic API.")
        except Exception:
            # Anything unexpected: log it server-side, but still end the stream cleanly for the UI.
            logger.exception("Chat generation failed")
            yield sse("error", "Something went wrong generating the answer. Check the server logs.")
        yield sse("done", None)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
