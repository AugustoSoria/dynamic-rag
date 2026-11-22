import { Loader2, Menu } from "lucide-react";
import { lazy, Suspense, useState } from "react";

import type { DocumentInfo, Source } from "../api/types";
import { useChat } from "../hooks/useChat";
import { useDocuments } from "../hooks/useDocuments";
import { ChatPanel } from "./ChatPanel";
import type { ViewerTarget } from "./PdfViewer";
import { Sidebar } from "./Sidebar";

// pdf.js pesa ~700 KB: el visor se descarga recién la primera vez que se abre un PDF.
const PdfViewer = lazy(() => import("./PdfViewer").then((m) => ({ default: m.PdfViewer })));

interface Props {
  sessionId: string;
  onNewSession: () => void;
}

export function Workspace({ sessionId, onNewSession }: Props) {
  const docs = useDocuments(sessionId);
  const chat = useChat(sessionId, docs.selectedIds);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [viewer, setViewer] = useState<ViewerTarget | null>(null);

  // Si el documento abierto se elimina, el visor se cierra solo (estado derivado, sin efectos).
  const viewerDoc = viewer ? docs.documents.find((d) => d.doc_id === viewer.docId) : undefined;

  const openSource = (source: Source) =>
    setViewer((v) => ({
      docId: source.doc_id,
      page: source.page,
      highlight: { page: source.page, text: source.text },
      focusId: (v?.focusId ?? 0) + 1,
    }));

  const openDocument = (doc: DocumentInfo) => {
    setViewer((v) => ({ docId: doc.doc_id, page: 1, focusId: (v?.focusId ?? 0) + 1 }));
    setSidebarOpen(false);
  };

  return (
    <div className="flex h-full">
      {/* Mobile: fondo oscuro detrás del menú abierto */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-slate-900/40 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/*
        Una sola instancia del sidebar: fija a la izquierda en escritorio y menú deslizable en mobile.
        (Antes se renderizaba dos veces, una oculta con CSS, duplicando su DOM y su estado.)
      */}
      <aside
        className={`flex shrink-0 bg-white transition-[translate,visibility] duration-200 md:static md:w-80 md:border-r md:border-slate-200 max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:w-[85%] max-md:max-w-80 max-md:shadow-xl ${
          sidebarOpen ? "" : "max-md:invisible max-md:-translate-x-full"
        }`}
      >
        <Sidebar
          docs={docs}
          openDocId={viewerDoc?.doc_id}
          onOpenDocument={openDocument}
          onNewSession={onNewSession}
          onClose={() => setSidebarOpen(false)}
        />
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
            aria-label="Abrir documentos"
          >
            <Menu className="size-5" />
          </button>
          <span className="font-semibold text-slate-900">Dynamic RAG</span>
          <span className="ml-auto text-xs text-slate-500">
            {docs.documents.length} {docs.documents.length === 1 ? "documento" : "documentos"}
          </span>
        </div>

        <ChatPanel
          chat={chat}
          hasDocuments={docs.documents.length > 0}
          scopeLabel={scopeLabel(docs.documents.length, docs.selectedIds.length)}
          onOpenDocuments={() => setSidebarOpen(true)}
          onOpenSource={openSource}
        />
      </main>

      {/* Visor: panel lateral en pantallas grandes, pantalla completa en mobile/tablet */}
      {viewer && viewerDoc && (
        <section className="fixed inset-0 z-50 flex flex-col lg:static lg:z-auto lg:w-[45%] lg:max-w-[760px] lg:shrink-0 lg:border-l lg:border-slate-200">
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center bg-slate-100 text-slate-400">
                <Loader2 className="size-5 animate-spin" />
              </div>
            }
          >
            <PdfViewer
              key={viewerDoc.doc_id} // otro documento = estado del visor nuevo
              sessionId={sessionId}
              document={viewerDoc}
              target={viewer}
              onPageChange={(page) => setViewer((v) => (v ? { ...v, page } : v))}
              onClose={() => setViewer(null)}
            />
          </Suspense>
        </section>
      )}
    </div>
  );
}

function scopeLabel(total: number, selected: number): string {
  if (total === 0) return "Sin documentos";
  if (selected === 0 || selected === total)
    return total === 1 ? "Buscando en 1 documento" : `Buscando en los ${total} documentos`;
  return `Buscando en ${selected} de ${total} documentos`;
}
