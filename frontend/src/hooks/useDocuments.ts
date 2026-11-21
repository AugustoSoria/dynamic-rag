import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { deleteDocument, listDocuments, uploadDocument } from "../api/client";
import type { DocumentInfo } from "../api/types";

export const MAX_UPLOAD_MB = 20;

export type UploadStatus =
  | { state: "idle" }
  | { state: "uploading"; filename: string; progress: number }
  | { state: "processing"; filename: string }
  | { state: "error"; message: string };

function validatePdf(file: File) {
  if (!file.name.toLowerCase().endsWith(".pdf") && file.type !== "application/pdf") {
    throw new Error("Solo se aceptan archivos PDF.");
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
    throw new Error(`El archivo supera el máximo de ${MAX_UPLOAD_MB} MB.`);
  }
}

export function useDocuments(sessionId: string) {
  const queryClient = useQueryClient();
  const queryKey = ["documents", sessionId];

  // Lista de documentos: TanStack Query maneja carga, caché, reintentos y respuestas fuera de orden.
  const documentsQuery = useQuery({
    queryKey,
    queryFn: () => listDocuments(sessionId),
  });
  const documents = documentsQuery.data ?? [];

  // Documentos seleccionados para la búsqueda. Vacío = todos.
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Progreso de subida (0..1). Al llegar a 1 el backend empieza a procesar el PDF.
  const [uploadProgress, setUploadProgress] = useState(0);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      validatePdf(file); // si tira error, queda en uploadMutation.error como cualquier error del server
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
      setSelectedIds((ids) => ids.filter((id) => id !== docId));
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
    upload,
    uploadFile: (file: File) => uploadMutation.mutate(file),
    removeDocument: (docId: string) => deleteMutation.mutateAsync(docId),
    dismissUploadError: () => uploadMutation.reset(),
    selectedIds,
    toggleSelected,
  };
}
