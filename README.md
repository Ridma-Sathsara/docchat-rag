# DocChat: chat with your documents (RAG)

Upload PDFs, text or Markdown files and ask questions about them. Answers stream in
token by token and cite the exact passages they came from, which you can click to read.

**Stack:** Next.js 15 + Tailwind · FastAPI (Python) · PostgreSQL + pgvector · fastembed (local embeddings) · Claude API

## How it works

```
                 ┌────────────── INGEST ──────────────┐
 upload.pdf ──▶  extract text per page ──▶ split into overlapping chunks
                 ──▶ embed each chunk (bge-small, local CPU) ──▶ Postgres (pgvector + tsvector)

                 ┌────────────── QUERY ───────────────┐
 question  ──▶   embed question ──▶ vector search  ─┐
                 keyword search (full-text)  ───────┴─▶ Reciprocal Rank Fusion ──▶ top 6 chunks
                 ──▶ prompt Claude with numbered sources ──▶ streamed answer with [n] citations
```

| Piece | File | What to learn there |
|---|---|---|
| Text extraction + chunking | [backend/app/ingest.py](backend/app/ingest.py) | Chunk size/overlap tradeoffs, keeping page numbers for citations |
| Embeddings | [backend/app/embeddings.py](backend/app/embeddings.py) | Query vs passage embeddings, running a model locally |
| Schema + indexes | [backend/app/db.py](backend/app/db.py) | `vector(384)`, HNSW index, generated `tsvector` column |
| Hybrid retrieval | [backend/app/retrieval.py](backend/app/retrieval.py) | Why vector-only search misses exact terms; RRF in one SQL query |
| Generation | [backend/app/llm.py](backend/app/llm.py) | Grounding prompt, citation format, streaming, refusal handling |
| API + SSE | [backend/app/main.py](backend/app/main.py) | Server-Sent Events from FastAPI |
| SSE client | [frontend/src/lib/api.ts](frontend/src/lib/api.ts) | Parsing a streamed POST response (EventSource is GET-only) |
| Citations UI | [frontend/src/components/Answer.tsx](frontend/src/components/Answer.tsx) | Turning `[n]` markers into clickable chips |
| Retrieval eval | [backend/eval/retrieval_eval.py](backend/eval/retrieval_eval.py) | Measuring hit@k and MRR before and after a change |

## Run it locally

You need Docker Desktop, Python 3.11+, Node 20+ and an [Anthropic API key](https://console.anthropic.com).

**1. Database**

```bash
docker compose up -d
```

**2. Backend** (from `backend/`)

```bash
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env
```

Put your key in `backend/.env` as `ANTHROPIC_API_KEY=...`, then:

```bash
uvicorn app.main:app --reload --port 8000
```

The first upload downloads the embedding model (~130 MB) once. API docs: http://localhost:8000/docs

**3. Frontend** (from `frontend/`)

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/documents` | Upload and index a file (multipart `file`) |
| `GET` | `/documents` | List indexed documents |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks |
| `POST` | `/search` | Retrieval only, no LLM. Use it to debug what the model sees |
| `POST` | `/chat` | SSE stream: `sources` → `delta`… → `done` (or `error`) |

## Measuring retrieval quality

Create `backend/eval/questions.jsonl` with questions you know the answer location for:

```json
{"question": "What is the refund window?", "filename": "policy.pdf", "page": 4}
```

```bash
python -m eval.retrieval_eval --k 6
```

Change `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K` or `EMBEDDING_MODEL` in `.env`, re-upload and re-run to compare. If you change
`EMBEDDING_MODEL`, also change `embedding_dim` in `config.py` and recreate the database (`docker compose down -v`).

## Cost

Embeddings run locally and cost nothing. Each question sends roughly 6 chunks (~2,000 tokens) to Claude.
The default model is `claude-opus-5-5`; set `CLAUDE_MODEL=claude-haiku-5-5` in `.env` for a much cheaper model
while you experiment.

## Troubleshooting (Windows)

- **"path length … exceeds max length" or "DLL load failed … filename too long":** keep the project in a short path such as `F:\docchat`.
- **Requests hang forever:** check that the database container is running (`docker ps`). If it stopped, run `docker compose up -d` again.
- **"A required privilege is not held" while downloading the embedding model:** harmless. fastembed falls back to another download source. Turning on Windows Developer Mode removes the warning.

## Ideas for v2

- **Query rewriting:** turn follow-ups like "what about the second one?" into standalone questions before retrieval
- **Re-ranking:** retrieve 30 chunks, re-score them with a cross-encoder, keep the best 6
- **Answer evals:** use an LLM judge to score faithfulness (is every claim supported by its cited source?)
- **OCR** for scanned PDFs, plus DOCX and HTML support
- **Auth + per-user documents**, then deploy (Vercel for the frontend, Fly.io/Render/AWS for the API, Neon or Supabase for pgvector)
