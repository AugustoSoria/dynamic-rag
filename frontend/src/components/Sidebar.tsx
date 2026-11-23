import { FileSearch, PanelLeftClose, RotateCcw, X } from "lucide-react";

import type { DocumentInfo } from "../api/types";
import type { useDocuments } from "../hooks/useDocuments";
import { DocumentList } from "./DocumentList";
import { UploadZone } from "./UploadZone";

interface Props {
  docs: ReturnType<typeof useDocuments>;
  openDocId?: string;
  onOpenDocument: (doc: DocumentInfo) => void;
  onNewSession: () => void;
  onClose: () => void;
  /** Pliega el panel (solo escritorio), para dar más lugar al chat y al visor. */
  onCollapse: () => void;
}

export function Sidebar({ docs, openDocId, onOpenDocument, onNewSession, onClose, onCollapse }: Props) {
  const handleNewSession = () => {
    if (
      docs.documents.length === 0 ||
      confirm("¿Empezar una sesión nueva? Vas a dejar de ver los documentos actuales.")
    ) {
      onNewSession();
    }
  };

  return (
    <div className="flex w-full flex-col">
      <header className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <div className="flex size-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
          <FileSearch className="size-5" />
        </div>
        <div className="min-w-0">
          <h1 className="font-semibold text-slate-900">Dynamic RAG</h1>
          <p className="text-xs text-slate-500">Chateá con tus PDFs</p>
        </div>
        <button
          onClick={onCollapse}
          className="ml-auto hidden rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 md:block"
          aria-label="Ocultar documentos"
          title="Ocultar documentos"
        >
          <PanelLeftClose className="size-5" />
        </button>
        <button
          onClick={onClose}
          className="ml-auto rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 md:hidden"
          aria-label="Cerrar"
        >
          <X className="size-5" />
        </button>
      </header>

      <div className="px-5">
        <UploadZone
          status={docs.upload}
          maxMb={docs.config?.max_upload_mb}
          disabledReason={
            docs.limitReached ? `Máximo de ${docs.config?.max_documents_per_session} documentos alcanzado` : undefined
          }
          onFile={docs.uploadFile}
          onDismissError={docs.dismissUploadError}
        />
      </div>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-5">
        <DocumentList
          documents={docs.documents}
          loading={docs.loading}
          loadError={docs.loadError}
          onRetry={docs.retryLoad}
          selectedIds={docs.selectedIds}
          onToggle={docs.toggleSelected}
          onDelete={docs.removeDocument}
          openDocId={openDocId}
          onOpen={onOpenDocument}
        />
      </div>

      <footer className="space-y-2 border-t border-slate-200 px-5 py-3">
        {docs.config && (
          <p className="text-[11px] leading-snug text-slate-400">
            Los documentos se eliminan automáticamente tras {formatMinutes(docs.config.session_ttl_minutes)} sin
            actividad.
          </p>
        )}
        <button
          onClick={handleNewSession}
          className="flex items-center gap-2 text-sm text-slate-500 transition hover:text-slate-800"
        >
          <RotateCcw className="size-4" />
          Nueva sesión
        </button>
      </footer>
    </div>
  );
}

function formatMinutes(minutes: number): string {
  if (minutes % 60 !== 0) return `${minutes} minutos`;
  const hours = minutes / 60;
  return hours === 1 ? "1 hora" : `${hours} horas`;
}
