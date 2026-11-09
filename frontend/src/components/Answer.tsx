"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Source } from "@/lib/api";

type Props = {
  text: string;
  sources: Source[];
  onCite: (source: Source) => void;
};

/** Render the model's Markdown, turning [n] markers into clickable citation chips. */
export default function Answer({ text, sources, onCite }: Props) {
  // [3] -> [3](#cite-3) so the Markdown parser hands it to our custom link renderer.
  const linked = text.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");

  return (
    <div className="prose prose-sm max-w-none dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const match = href?.match(/^#cite-(\d+)$/);
            const source = match && sources.find((s) => s.n === Number(match[1]));
            if (!source) {
              return (
                <a href={href} target="_blank" rel="noreferrer" className="text-indigo-600 underline">
                  {children}
                </a>
              );
            }
            return (
              <button
                type="button"
                onClick={() => onCite(source)}
                title={`${source.filename}${source.page ? `, p. ${source.page}` : ""}`}
                className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-indigo-100 px-1 align-text-top text-[11px] font-semibold text-indigo-700 hover:bg-indigo-200 dark:bg-indigo-900/60 dark:text-indigo-300"
              >
                {source.n}
              </button>
            );
          },
        }}
      >
        {linked}
      </ReactMarkdown>
    </div>
  );
}
