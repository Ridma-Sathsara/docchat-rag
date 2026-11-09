"use client";

import { useCallback, useEffect, useState } from "react";
import Chat from "@/components/Chat";
import DocumentPanel from "@/components/DocumentPanel";
import { API_URL, listDocuments, type DocumentInfo } from "@/lib/api";

export default function Home() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loadError, setLoadError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
      setLoadError(null);
      // Drop selections for documents that no longer exist.
      setSelected((prev) => new Set([...prev].filter((id) => docs.some((d) => d.id === id))));
    } catch {
      setLoadError(`Can't reach the backend at ${API_URL}. Is it running?`);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const panel = (
    <DocumentPanel
      documents={documents}
      selected={selected}
      onToggle={toggle}
      onChanged={refresh}
      loadError={loadError}
    />
  );

  return (
    <main className="flex h-dvh flex-col md:flex-row">
      {/* Mobile: top bar with a drawer. Desktop: fixed sidebar. */}
      <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-2 md:hidden dark:border-zinc-800">
        <span className="font-semibold">DocChat</span>
        <button
          type="button"
          onClick={() => setPanelOpen(true)}
          className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-700"
        >
          Documents ({documents.length})
        </button>
      </header>
      {panelOpen && (
        <div className="fixed inset-0 z-20 flex md:hidden">
          <div className="w-72 max-w-[85vw] bg-white dark:bg-zinc-950">{panel}</div>
          <button
            type="button"
            aria-label="Close documents"
            onClick={() => setPanelOpen(false)}
            className="flex-1 bg-black/40"
          />
        </div>
      )}
      <div className="hidden w-72 shrink-0 md:block">{panel}</div>
      <Chat documentIds={selected.size ? [...selected] : null} hasDocuments={documents.length > 0} />
    </main>
  );
}
