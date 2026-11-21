import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { Suspense, useCallback, useMemo, useRef, useState } from "react";
import { Document, Page } from "react-pdf";

import { fetchDocumentFile } from "../api/client";
import type { DocumentInfo } from "../api/types";
import { escapeHtml, findHighlightedItems, type TextItemLike } from "../lib/highlight";
import "../lib/pdf";

export interface ViewerTarget {
  docId: string;
  page: number;
  /** Fragmento a resaltar (viene de una cita). */
  highlight?: { page: number; text: string };
  /** Cambia en cada clic, para volver a enfocar aunque sea la misma cita. */
  focusId: number;
}

interface Props {
  sessionId: string;
  document: DocumentInfo;
  target: ViewerTarget;
  onPageChange: (page: number) => void;
  onClose: () => void;
}

const NO_HIGHLIGHT = new Set<number>();

export function PdfViewer({ sessionId, document: doc, target, onPageChange, onClose }: Props) {
  const file = useQuery({
    queryKey: ["document-file", sessionId, doc.doc_id],
    queryFn: () => fetchDocumentFile(sessionId, doc.doc_id),
    staleTime: Infinity, // el PDF no cambia nunca
  });

  // Total real de páginas (el backend solo cuenta las que tienen texto).
  const [numPages, setNumPages] = useState<number | null>(null);
  const [width, setWidth] = useState(0);
  const [pageText, setPageText] = useState<{ page: number; items: TextItemLike[] } | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const page = target.page;
  const highlightText = target.highlight?.page === page ? target.highlight.text : null;

  const highlighted = useMemo(
    () =>
      highlightText && pageText?.page === page ? findHighlightedItems(pageText.items, highlightText) : NO_HIGHLIGHT,
    [highlightText, pageText, page],
  );

  const textRenderer = useCallback(
    ({ str, itemIndex }: { str: string; itemIndex: number }) =>
      highlighted.has(itemIndex) ? `<mark>${escapeHtml(str)}</mark>` : escapeHtml(str),
    [highlighted],
  );

  // Ref callback con cleanup (React 19): mide el ancho disponible sin usar useEffect.
  const measureRef = useCallback((el: HTMLDivElement | null) => {
    scrollRef.current = el;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Debe ser estable: react-pdf vuelve a dibujar la capa de texto si este callback cambia, y el
  // Workspace se re-renderiza con cada token del chat (el visor saltaría al resaltado una y otra vez).
  const scrollToHighlight = useCallback(() => {
    scrollRef.current?.querySelector("mark")?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, []);

  const total = numPages ?? doc.num_pages;
  const goTo = (p: number) => onPageChange(Math.min(Math.max(1, p), total));

  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-100">
      <header className="flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-800" title={doc.filename}>
            {doc.filename}
          </p>
        </div>
        <div className="flex items-center gap-1 text-sm text-slate-600">
          <button
            onClick={() => goTo(page - 1)}
            disabled={page <= 1}
            className="rounded p-1 hover:bg-slate-100 disabled:opacity-30"
            aria-label="Página anterior"
          >
            <ChevronLeft className="size-4" />
          </button>
          <span className="min-w-[70px] text-center tabular-nums">
            {page} / {total}
          </span>
          <button
            onClick={() => goTo(page + 1)}
            disabled={page >= total}
            className="rounded p-1 hover:bg-slate-100 disabled:opacity-30"
            aria-label="Página siguiente"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
        <button
          onClick={onClose}
          className="ml-1 rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          aria-label="Cerrar visor"
        >
          <X className="size-5" />
        </button>
      </header>

      <div ref={measureRef} className="min-h-0 flex-1 overflow-auto p-3">
        {file.isPending && <CenteredMessage icon={<Loader2 className="size-5 animate-spin" />} text="Cargando PDF…" />}
        {file.isError && <CenteredMessage icon={<AlertCircle className="size-5" />} text={file.error.message} />}
        {file.data && width > 0 && (
          // react-pdf suspende mientras carga cada página: este límite evita que el visor entero
          // (encabezado incluido) se reemplace por el fallback del lazy() al cambiar de página.
          <Suspense fallback={<div style={{ height: (width - 24) * 1.3 }} className="mx-auto rounded bg-white" />}>
            <Document
              file={file.data}
              onLoadSuccess={(pdf) => setNumPages(pdf.numPages)}
              loading={<CenteredMessage icon={<Loader2 className="size-5 animate-spin" />} text="Abriendo PDF…" />}
              error={<CenteredMessage icon={<AlertCircle className="size-5" />} text="No se pudo abrir el PDF." />}
            >
              <Page
                // focusId en la key: volver a hacer clic en la misma cita re-renderiza y vuelve a enfocar.
                key={`${page}-${target.focusId}`}
                pageNumber={page}
                width={width - 24}
                className="mx-auto overflow-hidden rounded shadow-md"
                customTextRenderer={textRenderer}
                onGetTextSuccess={(text) => setPageText({ page, items: text.items })}
                onRenderTextLayerSuccess={scrollToHighlight}
                renderAnnotationLayer={false}
                loading={<div style={{ height: (width - 24) * 1.3 }} className="mx-auto rounded bg-white" />}
              />
            </Document>
          </Suspense>
        )}
      </div>

      {target.highlight && target.highlight.page !== page && (
        <button
          onClick={() => goTo(target.highlight!.page)}
          className="border-t border-slate-200 bg-white py-2 text-xs text-indigo-600 hover:bg-indigo-50"
        >
          Volver al fragmento citado (pág. {target.highlight.page})
        </button>
      )}
    </div>
  );
}

function CenteredMessage({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 py-20 text-sm text-slate-500">
      {icon}
      {text}
    </div>
  );
}
