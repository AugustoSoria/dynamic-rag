import ReactMarkdown, { type Components } from "react-markdown";

import type { Source } from "../api/types";

interface Props {
  content: string;
  sources?: Source[];
  streaming?: boolean;
}

const CITATION_HREF = "#cite-";

/** Convierte las citas [n] en links internos para poder renderizarlas como chips. */
function linkCitations(text: string): string {
  return text.replace(/\[(\d{1,2})\](?!\()/g, (_, n) => `[${n}](${CITATION_HREF}${n})`);
}

export function Markdown({ content, sources = [], streaming }: Props) {
  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith(CITATION_HREF)) {
        const index = Number(href.slice(CITATION_HREF.length));
        const source = sources.find((s) => s.index === index);
        return (
          <span
            title={source ? `${source.filename} · página ${source.page}` : undefined}
            className="mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md bg-indigo-100 px-1 align-middle text-[11px] font-semibold text-indigo-700"
          >
            {index}
          </span>
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
