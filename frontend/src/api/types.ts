export interface PublicConfig {
  max_upload_mb: number;
  max_pages: number;
  max_documents_per_session: number;
  session_ttl_minutes: number;
}

export interface DocumentInfo {
  doc_id: string;
  filename: string;
  num_pages: number;
  num_chunks: number;
  created_at: string;
}

/** Procesamiento en segundo plano de un PDF subido (ver backend/app/services/jobs.py). */
export interface JobStatus {
  doc_id: string;
  filename: string;
  status: "queued" | "processing" | "ready" | "error";
  processed: number;
  total: number;
  queue_position: number;
  elapsed_seconds: number;
  error: string | null;
  document: DocumentInfo | null;
}

export interface Source {
  index: number;
  doc_id: string;
  filename: string;
  page: number;
  text: string;
  score: number;
}

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  question: string;
  history: HistoryMessage[];
  doc_ids: string[] | null;
}
