"use client";

import { useRef, useState } from "react";
import { deleteDocument, uploadDocument, type DocumentInfo } from "@/lib/api";

type Props = {
  documents: DocumentInfo[];
  selected: Set<number>;
  onToggle: (id: number) => void;
  onChanged: () => void;
  loadError: string | null;
};

export default function DocumentPanel({ documents, selected, onToggle, onChanged, loadError }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    for (const file of Array.from(files)) {
      setUploading(file.name);
      try {
        await uploadDocument(file);
      } catch (e) {
        setError(`${file.name}: ${(e as Error).message}`);
      }
    }
    setUploading(null);
    onChanged();
  }

  async function handleDelete(doc: DocumentInfo) {
    if (!confirm(`Delete "${doc.filename}" and its indexed chunks?`)) return;
    try {
      await deleteDocument(doc.id);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <aside className="flex h-full flex-col gap-4 border-r border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/50">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">Documents</h2>

      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        disabled={!!uploading}
        className={`rounded-lg border-2 border-dashed px-4 py-6 text-sm transition ${
          dragging
            ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40"
            : "border-zinc-300 hover:border-indigo-400 dark:border-zinc-700"
        } disabled:cursor-wait disabled:opacity-60`}
      >
        {uploading ? (
          <span>Indexing {uploading}…</span>
        ) : (
          <span>
            <strong className="text-indigo-600 dark:text-indigo-400">Upload</strong> or drop PDF, TXT, MD
          </span>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md"
        multiple
        hidden
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />

      {(error || loadError) && (
        <p className="rounded-md bg-red-50 p-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-300">
          {error || loadError}
        </p>
      )}

      <ul className="flex-1 space-y-1 overflow-y-auto">
        {documents.length === 0 && !loadError && (
          <li className="text-sm text-zinc-500">No documents yet.</li>
        )}
        {documents.map((doc) => (
          <li
            key={doc.id}
            className="group flex items-start gap-2 rounded-md px-2 py-2 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <input
              type="checkbox"
              className="mt-1 accent-indigo-600"
              checked={selected.has(doc.id)}
              onChange={() => onToggle(doc.id)}
              aria-label={`Search in ${doc.filename}`}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium" title={doc.filename}>
                {doc.filename}
              </p>
              <p className="text-xs text-zinc-500">
                {doc.num_pages ? `${doc.num_pages} pages · ` : ""}
                {doc.num_chunks} {doc.num_chunks === 1 ? "chunk" : "chunks"}
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleDelete(doc)}
              className="text-xs text-zinc-400 opacity-0 hover:text-red-600 group-hover:opacity-100"
              aria-label={`Delete ${doc.filename}`}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>

      <p className="text-xs text-zinc-500">
        {selected.size === 0 ? "Searching all documents" : `Searching ${selected.size} selected`}
      </p>
    </aside>
  );
}
