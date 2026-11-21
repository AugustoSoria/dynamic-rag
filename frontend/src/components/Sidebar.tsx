import { FileSearch, RotateCcw, X } from "lucide-react";

import type { useDocuments } from "../hooks/useDocuments";
import { DocumentList } from "./DocumentList";
import { UploadZone } from "./UploadZone";

interface Props {
  docs: ReturnType<typeof useDocuments>;
  onNewSession: () => void;
  onClose: () => void;
}

export function Sidebar({ docs, onNewSession, onClose }: Props) {
  const handleNewSession = () => {
    if (docs.documents.length === 0 || confirm("¿Empezar una sesión nueva? Vas a dejar de ver los documentos actuales.")) {
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
          onClick={onClose}
          className="ml-auto rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 md:hidden"
          aria-label="Cerrar"
        >
          <X className="size-5" />
        </button>
      </header>

      <div className="px-5">
        <UploadZone status={docs.upload} onFile={docs.uploadFile} onDismissError={docs.dismissUploadError} />
      </div>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto px-5">
        <DocumentList
          documents={docs.documents}
          loading={docs.loading}
          selectedIds={docs.selectedIds}
          onToggle={docs.toggleSelected}
          onDelete={docs.removeDocument}
        />
      </div>

      <footer className="border-t border-slate-200 px-5 py-3">
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
