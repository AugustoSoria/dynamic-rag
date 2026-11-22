import ReactMarkdown, { type Components } from "react-markdown";

import type { Source } from "../api/types";
import { CITATION_HREF, linkCitations } from "../lib/citations";

interface Props {
  content: string;
  sources?: Source[];
  streaming?: boolean;
  onOpenSource?: (source: Source) => void;
}

export function Markdown({ content, sources = [], streaming, onOpenSource }: Props) {
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith(CITATION_HREF)) {
        const index = Number(href.slice(CITATION_HREF.length));
        const source = sources.find((s) => s.index === index);
        const chipClass =
          "mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md bg-indigo-100 px-1 align-middle text-[11px] font-semibold text-indigo-700";
        // Una cita a una fuente que no existe (el modelo se equivocó de número) se muestra pero no es clickeable.
        if (!source || !onOpenSource) return <span className={chipClass}>{index}</span>;
        return (
          <button
            type="button"
            onClick={() => onOpenSource(source)}
            title={`Ver en ${source.filename} · página ${source.page}`}
            className={`${chipClass} cursor-pointer transition hover:bg-indigo-600 hover:text-white`}
          >
            {index}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noreferrer" className="text-indigo-600 underline">
          {children}
        </a>
      );
    },
  };

  return (
    <div className={`markdown ${streaming ? "streaming-cursor" : ""}`}>
      <ReactMarkdown components={components}>{linkCitations(content)}</ReactMarkdown>
    </div>
  );
}
