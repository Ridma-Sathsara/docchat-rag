"""Answer generation with Claude, grounded in retrieved chunks and citing them as [n]."""

import os
from collections.abc import Iterator
from functools import lru_cache

import anthropic

from .config import get_settings

SYSTEM_PROMPT = """You answer questions using only the numbered sources provided in the user's message.

Cite every claim with the source number in square brackets, like [1] or [2][3], placed right after the claim. \
If the sources don't contain the answer, say so plainly and don't fill the gap from general knowledge. \
Keep answers concise and use Markdown for lists or tables when it helps."""

class MissingAPIKey(RuntimeError):
    pass


@lru_cache
def _client() -> anthropic.Anthropic:
    # pydantic-settings reads backend/.env but doesn't export it, so pass the key through.
    key = get_settings().anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise MissingAPIKey("ANTHROPIC_API_KEY is not set. Add it to backend/.env and restart the server.")
    return anthropic.Anthropic(api_key=key)


def build_context(sources: list[dict]) -> str:
    parts = []
    for i, s in enumerate(sources, start=1):
        where = s["filename"] + (f", page {s['page']}" if s["page"] else "")
        parts.append(f'<source id="{i}" location="{where}">\n{s["content"]}\n</source>')
    return "\n\n".join(parts)


def stream_answer(question: str, sources: list[dict], history: list[dict]) -> Iterator[str]:
    """Yield answer text deltas. Earlier turns are passed as plain text for follow-up questions."""
    s = get_settings()
    user_turn = (
        f"<sources>\n{build_context(sources)}\n</sources>\n\nQuestion: {question}"
        if sources
        else f"(No matching sources were found in the uploaded documents.)\n\nQuestion: {question}"
    )
    messages = [*history, {"role": "user", "content": user_turn}]

    with _client().beta.messages.stream(
        model=s.claude_model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": s.claude_effort},
        # If a safety classifier declines, the API retries on Anthropic's recommended fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text
        final = stream.get_final_message()

    if final.stop_reason == "refusal":
        yield "\n\n_The model declined to answer this question._"
    elif final.stop_reason == "max_tokens":
        yield "\n\n_(Answer truncated: hit the output limit.)_"
