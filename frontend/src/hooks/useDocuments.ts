import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, deleteDocument, fetchJob, listActiveJobs, listDocuments, uploadDocument } from "../api/client";
import type { DocumentInfo, JobStatus, PublicConfig } from "../api/types";
import { useConfig } from "./useConfig";

export type UploadStatus =
  | { state: "idle" }
  | { state: "uploading"; filename: string; progress: number }
  | { state: "reading"; filename: string } // archivo subido, el backend extrae el texto (< 1 s)
  | { state: "queued"; filename: string; position: number }
  | { state: "processing"; filename: string; processed: number; total: number; etaSeconds: number | null }
  | { state: "error"; message: string };

export const documentsQueryKey = (sessionId: string) => ["documents", sessionId];

const POLL_INTERVAL_MS = 1000;
const isActive = (job: JobStatus | undefined) => job?.status === "queued" || job?.status === "processing";

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

/** Tiempo restante estimado a partir del ritmo observado (null hasta tener una muestra confiable). */
function estimateEta(job: JobStatus): number | null {
  if (job.processed === 0 || job.elapsed_seconds < 2) return null;
  const perChunk = job.elapsed_seconds / job.processed;
  return Math.max(0, Math.round(perChunk * (job.total - job.processed)));
}

export function useDocuments(sessionId: string) {
  const queryClient = useQueryClient();
  const config = useConfig();
  const queryKey = documentsQueryKey(sessionId);

  // Lista de documentos listos: TanStack Query maneja carga, caché, reintentos y respuestas fuera de orden.
  const documentsQuery = useQuery({
    queryKey,
    queryFn: () => listDocuments(sessionId),
  });
  const documents = documentsQuery.data ?? [];

  // Documentos seleccionados para la búsqueda. Vacío = todos.
  // Se filtran contra la lista actual: si un documento desaparece (borrado o sesión vencida), deja de contar.
  const [rawSelectedIds, setSelectedIds] = useState<string[]>([]);
  const selectedIds = rawSelectedIds.filter((id) => documents.some((d) => d.doc_id === id));

  // --- Subida + procesamiento en segundo plano --------------------------------------

  // Trabajos que ya estaban en curso al abrir la página (p. ej. si el usuario recargó a mitad de proceso).
  const resumableJobs = useQuery({
    queryKey: ["jobs", sessionId],
    queryFn: () => listActiveJobs(sessionId),
    staleTime: Infinity,
  });

  // Trabajo que seguimos. undefined = todavía no elegimos (retomamos uno en curso si lo hay); null = ninguno.
  const [chosenJobId, setChosenJobId] = useState<string | null | undefined>(undefined);
  const trackedJobId = chosenJobId === undefined ? (resumableJobs.data?.[0]?.doc_id ?? null) : chosenJobId;

  const jobQuery = useQuery({
    queryKey: ["job", sessionId, trackedJobId],
    queryFn: async () => {
      const job = await fetchJob(sessionId, trackedJobId!);
      if (job.status === "ready" && job.document) {
        // El documento terminó: lo sumamos a la lista (sin duplicarlo si la consulta se repite).
        const doc = job.document;
        queryClient.setQueryData<DocumentInfo[]>(queryKey, (docs = []) =>
          docs.some((d) => d.doc_id === doc.doc_id) ? docs : [...docs, doc],
        );
      }
      return job;
    },
    enabled: !!trackedJobId,
    // Se consulta cada segundo mientras está activo, y se deja de consultar al terminar.
    refetchInterval: (query) => (isActive(query.state.data) ? POLL_INTERVAL_MS : false),
    // 404 = el trabajo ya no existe (servidor reiniciado o expirado): no tiene sentido reintentar.
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 2,
  });
  const job = trackedJobId ? jobQuery.data : undefined;

  // Progreso de la subida del archivo (0..1).
  const [uploadProgress, setUploadProgress] = useState(0);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      validateUpload(file, config, documents.length + (isActive(job) ? 1 : 0));
      setUploadProgress(0);
      return uploadDocument(sessionId, file, setUploadProgress);
    },
    onSuccess: (newJob) => {
      // Sembramos la caché con la respuesta de la subida: el progreso se muestra sin esperar la primera consulta.
      queryClient.setQueryData(["job", sessionId, newJob.doc_id], newJob);
      setChosenJobId(newJob.doc_id);
    },
  });

  // El estado que ve el usuario se deriva de la mutación y del trabajo: no hay estado duplicado que sincronizar.
  const upload: UploadStatus = (() => {
    if (uploadMutation.isPending) {
      const filename = uploadMutation.variables.name;
      return uploadProgress < 1
        ? { state: "uploading", filename, progress: uploadProgress }
        : { state: "reading", filename };
    }
    if (uploadMutation.isError) return { state: "error", message: uploadMutation.error.message };
    if (!job) return { state: "idle" };
    switch (job.status) {
      case "queued":
        return { state: "queued", filename: job.filename, position: job.queue_position };
      case "processing":
        return {
          state: "processing",
          filename: job.filename,
          processed: job.processed,
          total: job.total,
          etaSeconds: estimateEta(job),
        };
      case "error":
        return { state: "error", message: job.error ?? "No se pudo procesar el documento." };
      default:
        return { state: "idle" };
    }
  })();

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(sessionId, docId),
    onSuccess: (_, docId) => {
      queryClient.setQueryData<DocumentInfo[]>(queryKey, (docs = []) => docs.filter((d) => d.doc_id !== docId));
    },
  });

  const toggleSelected = (docId: string) =>
    setSelectedIds((ids) => (ids.includes(docId) ? ids.filter((id) => id !== docId) : [...ids, docId]));

  const inUse = documents.length + (isActive(job) ? 1 : 0);

  return {
    documents,
    loading: documentsQuery.isPending,
    loadError: documentsQuery.isError ? documentsQuery.error.message : null,
    retryLoad: () => documentsQuery.refetch(),
    config,
    limitReached: !!config && inUse >= config.max_documents_per_session,
    upload,
    uploadFile: (file: File) => uploadMutation.mutate(file),
    removeDocument: (docId: string) => deleteMutation.mutateAsync(docId),
    dismissUploadError: () => {
      uploadMutation.reset();
      setChosenJobId(null);
    },
    selectedIds,
    toggleSelected,
  };
}
