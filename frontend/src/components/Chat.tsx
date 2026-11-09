"use client";

import { useEffect, useRef, useState } from "react";
import Answer from "./Answer";
import { streamChat, type ChatTurn, type Source } from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  error?: string;
  pending?: boolean;
};

type Props = {
  documentIds: number[] | null;
  hasDocuments: boolean;
};

export default function Chat({ documentIds, hasDocuments }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  function updateLast(patch: (m: Message) => Message) {
    setMessages((prev) => [...prev.slice(0, -1), patch(prev[prev.length - 1])]);
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;

    const history: ChatTurn[] = messages
      .filter((m) => !m.error && m.content)
      .map(({ role, content }) => ({ role, content }));

    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", pending: true },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamChat(
        { question, history, document_ids: documentIds },
        {
          onSources: (sources) => updateLast((m) => ({ ...m, sources })),
          onDelta: (text) => updateLast((m) => ({ ...m, content: m.content + text })),
          onError: (error) => updateLast((m) => ({ ...m, error })),
        },
        controller.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        updateLast((m) => ({ ...m, error: `Could not reach the backend: ${(err as Error).message}` }));
      }
    } finally {
      updateLast((m) => ({ ...m, pending: false }));
      setBusy(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          {messages.length === 0 ? (
            <div className="mx-auto mt-24 max-w-md text-center text-zinc-500">
              <h1 className="mb-2 text-2xl font-semibold text-zinc-800 dark:text-zinc-100">Chat with your documents</h1>
              <p className="text-sm">
                {hasDocuments
                  ? "Ask a question. Answers cite the exact passages they come from."
                  : "Upload a PDF, TXT or Markdown file on the left to get started."}
              </p>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-6">
              {messages.map((m, i) =>
                m.role === "user" ? (
                  <div key={i} className="flex justify-end">
                    <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-sm text-white">
                      {m.content}
                    </p>
                  </div>
                ) : (
                  <div key={i} className="space-y-2">
                    {m.pending && !m.content && !m.error && (
                      <p className="animate-pulse text-sm text-zinc-500">
                        {m.sources ? `Read ${m.sources.length} passages, writing answer…` : "Searching documents…"}
                      </p>
                    )}
                    {m.content && (
                      <Answer text={m.content} sources={m.sources ?? []} onCite={setActiveSource} />
                    )}
                    {m.error && (
                      <p className="rounded-md bg-red-50 p-2 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-300">
                        {m.error}
                      </p>
                    )}
                    {!m.pending && m.sources && m.sources.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {m.sources.map((s) => (
                          <button
                            key={s.n}
                            type="button"
                            onClick={() => setActiveSource(s)}
                            className="rounded-full border border-zinc-200 px-2.5 py-0.5 text-xs text-zinc-600 hover:border-indigo-400 hover:text-indigo-700 dark:border-zinc-700 dark:text-zinc-400"
                          >
                            [{s.n}] {s.filename}
                            {s.page ? ` p.${s.page}` : ""}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ),
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <form onSubmit={send} className="border-t border-zinc-200 p-4 dark:border-zinc-800">
          <div className="mx-auto flex max-w-3xl gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  e.currentTarget.form?.requestSubmit();
                }
              }}
              rows={1}
              placeholder={hasDocuments ? "Ask about your documents…" : "Upload a document first"}
              disabled={!hasDocuments}
              className="flex-1 resize-none rounded-xl border border-zinc-300 bg-white px-4 py-2.5 text-sm outline-none focus:border-indigo-500 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900"
            />
            {busy ? (
              <button
                type="button"
                onClick={() => abortRef.current?.abort()}
                className="rounded-xl border border-zinc-300 px-4 text-sm dark:border-zinc-700"
              >
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() || !hasDocuments}
                className="rounded-xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40"
              >
                Send
              </button>
            )}
          </div>
        </form>
      </section>

      {activeSource && (
        // Bottom sheet on small screens, side panel on large ones.
        <aside className="fixed inset-x-0 bottom-0 z-30 flex max-h-[60dvh] flex-col border-t border-zinc-200 bg-zinc-50 shadow-2xl lg:static lg:max-h-none lg:w-96 lg:shrink-0 lg:border-t-0 lg:border-l lg:shadow-none dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex items-start justify-between gap-2 border-b border-zinc-200 p-4 dark:border-zinc-800">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Source [{activeSource.n}]</p>
              <p className="truncate text-sm font-medium">{activeSource.filename}</p>
              <p className="text-xs text-zinc-500">
                {activeSource.page ? `Page ${activeSource.page} · ` : ""}relevance {activeSource.score.toFixed(3)}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setActiveSource(null)}
              className="text-zinc-400 hover:text-zinc-700"
              aria-label="Close source"
            >
              ✕
            </button>
          </div>
          <p className="flex-1 overflow-y-auto whitespace-pre-wrap p-4 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            {activeSource.content}
          </p>
        </aside>
      )}
    </div>
  );
}
