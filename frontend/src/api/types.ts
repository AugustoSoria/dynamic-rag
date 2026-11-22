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
