import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { deleteDocument, listDocuments, uploadDocument } from "../api/client";
import type { DocumentInfo, PublicConfig } from "../api/types";
import { useConfig } from "./useConfig";

export type UploadStatus =
  | { state: "idle" }
  | { state: "uploading"; filename: string; progress: number }
  | { state: "processing"; filename: string }
  | { state: "error"; message: string };

export const documentsQueryKey = (sessionId: string) => ["documents", sessionId];

/** Validación rápida en el cliente (evita subir 50 MB para que el servidor los rechace). El backend valida igual. */
function validateUpload(file: File, config: PublicConfig | undefined, currentCount: number) {
  if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
    throw new Error("Solo se aceptan archivos PDF.");
  }
  if (!config) return;
  if (file.size > config.max_upload_mb * 1024 * 1024) {
    throw new Error(`El archivo supera el máximo de ${config.max_upload_mb} MB.`);
  }
  if (currentCount >= config.max_documents_per_session) {
    throw new Error(
      `Alcanzaste el máximo de ${config.max_documents_per_session} documentos. Eliminá alguno para subir otro.`,
    );
  }
}

export function useDocuments(sessionId: string) {
  const queryClient = useQueryClient();
  const config = useConfig();
  const queryKey = documentsQueryKey(sessionId);

  // Lista de documentos: TanStack Query maneja carga, caché, reintentos y respuestas fuera de orden.
  const documentsQuery = useQuery({
    queryKey,
    queryFn: () => listDocuments(sessionId),
  });
  const documents = documentsQuery.data ?? [];

  // Documentos seleccionados para la búsqueda. Vacío = todos.
  // Se filtran contra la lista actual: si un documento desaparece (borrado o sesión vencida), deja de contar.
  const [rawSelectedIds, setSelectedIds] = useState<string[]>([]);
  const selectedIds = rawSelectedIds.filter((id) => documents.some((d) => d.doc_id === id));

  // Progreso de subida (0..1). Al llegar a 1 el backend empieza a procesar el PDF.
  const [uploadProgress, setUploadProgress] = useState(0);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      validateUpload(file, config, documents.length); // si tira error, queda en uploadMutation.error
      setUploadProgress(0);
      return uploadDocument(sessionId, file, setUploadProgress);
    },
    onSuccess: (doc) => {
      // Actualizamos la caché directamente en lugar de volver a pedir la lista.
      queryClient.setQueryData<DocumentInfo[]>(queryKey, (docs = []) => [...docs, doc]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(sessionId, docId),
    onSuccess: (_, docId) => {
      queryClient.setQueryData<DocumentInfo[]>(queryKey, (docs = []) => docs.filter((d) => d.doc_id !== docId));
    },
  });

  // El estado de la subida se deriva de la mutación: no hay estado duplicado que sincronizar.
  const upload: UploadStatus = uploadMutation.isPending
    ? uploadProgress < 1
      ? { state: "uploading", filename: uploadMutation.variables.name, progress: uploadProgress }
      : { state: "processing", filename: uploadMutation.variables.name }
    : uploadMutation.isError
      ? { state: "error", message: uploadMutation.error.message }
      : { state: "idle" };

  const toggleSelected = (docId: string) =>
    setSelectedIds((ids) => (ids.includes(docId) ? ids.filter((id) => id !== docId) : [...ids, docId]));

  return {
    documents,
    loading: documentsQuery.isPending,
    loadError: documentsQuery.isError ? documentsQuery.error.message : null,
    retryLoad: () => documentsQuery.refetch(),
    config,
    limitReached: !!config && documents.length >= config.max_documents_per_session,
    upload,
    uploadFile: (file: File) => uploadMutation.mutate(file),
    removeDocument: (docId: string) => deleteMutation.mutateAsync(docId),
    dismissUploadError: () => uploadMutation.reset(),
    selectedIds,
    toggleSelected,
  };
}
