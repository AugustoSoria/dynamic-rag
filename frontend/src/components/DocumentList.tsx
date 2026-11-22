import { AlertCircle, FileText, Loader2, Trash2 } from "lucide-react";
import { useState } from "react";

import type { DocumentInfo } from "../api/types";

interface Props {
  documents: DocumentInfo[];
  loading: boolean;
  loadError: string | null;
  onRetry: () => void;
  selectedIds: string[];
  onToggle: (docId: string) => void;
  onDelete: (docId: string) => Promise<void>;
  openDocId?: string;
  onOpen: (doc: DocumentInfo) => void;
}

export function DocumentList({
  documents,
  loading,
  loadError,
  onRetry,
  selectedIds,
  onToggle,
  onDelete,
  openDocId,
  onOpen,
}: Props) {
  const [deleting, setDeleting] = useState<string | null>(null);

  if (loading) {
    return (
      <div className="flex justify-center py-6 text-slate-400">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  // Sin esto, un backend caído se vería igual que "no subiste documentos".
  if (loadError) {
    return (
      <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        <div>
          <p>No se pudieron cargar tus documentos.</p>
          <p className="text-xs text-red-600/80">{loadError}</p>
          <button onClick={onRetry} className="mt-1.5 text-xs font-medium underline hover:text-red-900">
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  if (documents.length === 0) {
    return <p className="py-2 text-sm text-slate-500">Todavía no subiste ningún documento.</p>;
  }

  const handleDelete = async (doc: DocumentInfo) => {
    if (!confirm(`¿Eliminar "${doc.filename}"?`)) return;
    setDeleting(doc.doc_id);
    try {
      await onDelete(doc.doc_id);
    } catch (err) {
      alert(err instanceof Error ? err.message : "No se pudo eliminar el documento.");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Documentos</h2>
        {documents.length > 1 && (
          <span className="text-xs text-slate-400">
            {selectedIds.length === 0 ? "Se usan todos" : `${selectedIds.length} seleccionados`}
          </span>
        )}
      </div>

      <ul className="space-y-1.5">
        {documents.map((doc) => {
          const selected = selectedIds.includes(doc.doc_id);
          return (
            <li
              data-testid="document-item"
              key={doc.doc_id}
              className={`group flex items-center gap-3 rounded-lg border p-2.5 transition ${
                selected ? "border-indigo-300 bg-indigo-50" : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              {documents.length > 1 && (
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => onToggle(doc.doc_id)}
                  className="size-4 shrink-0 accent-indigo-600"
                  aria-label={`Buscar solo en ${doc.filename}`}
                />
              )}
              <button
                type="button"
                onClick={() => onOpen(doc)}
                title={`Ver ${doc.filename}`}
                className="flex min-w-0 flex-1 items-center gap-3 text-left"
              >
                <FileText className="size-5 shrink-0 text-red-500" />
                <div className="min-w-0 flex-1">
                  <p
                    className={`truncate text-sm font-medium ${
                      openDocId === doc.doc_id ? "text-indigo-700" : "text-slate-800 hover:text-indigo-700"
                    }`}
                  >
                    {doc.filename}
                  </p>
                  <p className="text-xs text-slate-500">
                    {doc.num_pages} {doc.num_pages === 1 ? "página" : "páginas"} · {doc.num_chunks}{" "}
                    {doc.num_chunks === 1 ? "fragmento" : "fragmentos"}
                  </p>
                </div>
              </button>
              <button
                onClick={() => handleDelete(doc)}
                disabled={deleting === doc.doc_id}
                className="rounded p-1 text-slate-400 opacity-100 transition hover:bg-red-50 hover:text-red-600 md:opacity-0 md:group-hover:opacity-100"
                aria-label={`Eliminar ${doc.filename}`}
              >
                {deleting === doc.doc_id ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
              </button>
            </li>
          );
        })}
      </ul>

      {documents.length > 1 && (
        <p className="mt-2 text-xs text-slate-400">Marcá documentos para buscar solo en ellos.</p>
      )}
    </div>
  );
}
