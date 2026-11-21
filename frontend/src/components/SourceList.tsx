import { ChevronDown, FileText } from "lucide-react";
import { useState } from "react";

import type { Source } from "../api/types";

interface Props {
  sources: Source[];
  searchQuery?: string;
  question: string;
}

export function SourceList({ sources, searchQuery, question }: Props) {
  const [open, setOpen] = useState(false);
  if (sources.length === 0) return null;

  const rewritten = searchQuery && searchQuery.trim() !== question.trim();

  return (
    <div className="mt-3 border-t border-slate-100 pt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800"
      >
        <ChevronDown className={`size-3.5 transition ${open ? "rotate-180" : ""}`} />
        {sources.length} {sources.length === 1 ? "fuente" : "fuentes"}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {rewritten && (
            <p className="text-xs text-slate-500">
              Búsqueda: <span className="italic">“{searchQuery}”</span>
            </p>
          )}
          {sources.map((s) => (
            <div key={s.index} className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <div className="flex items-center gap-2 text-xs">
                <span className="flex size-[18px] items-center justify-center rounded-md bg-indigo-100 font-semibold text-indigo-700">
                  {s.index}
                </span>
                <FileText className="size-3.5 text-slate-400" />
                <span className="truncate font-medium text-slate-700">{s.filename}</span>
                <span className="shrink-0 text-slate-500">· pág. {s.page}</span>
                <span className="ml-auto shrink-0 text-slate-400" title="Similitud con la búsqueda">
                  {Math.round(s.score * 100)}%
                </span>
              </div>
              <p className="mt-1.5 line-clamp-3 text-xs whitespace-pre-line text-slate-600">{s.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
