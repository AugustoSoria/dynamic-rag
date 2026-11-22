import { createSSEParser } from "./sse";
import type { ChatRequest, DocumentInfo, PublicConfig, Source } from "./types";

const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

const CONNECTION_ERROR = "No se pudo conectar con el servidor. Revisá tu conexión o intentá en unos segundos.";

/**
 * Mensaje para el usuario a partir de una respuesta de error. Usa el `detail` del backend si lo hay;
 * si no (502/503/504 los genera un proxy cuando el backend no responde), un mensaje entendible.
 */
function errorMessage(status: number, detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (status === 0 || status === 502 || status === 503 || status === 504) return CONNECTION_ERROR;
  return `Error inesperado del servidor (${status}).`;
}

async function errorFromResponse(res: Response): Promise<ApiError> {
  let detail: unknown;
  try {
    detail = (await res.json()).detail;
  } catch {
    // respuesta sin JSON
  }
  return new ApiError(errorMessage(res.status, detail), res.status);
}

/** fetch que traduce los fallos de red y las respuestas de error a ApiError con un mensaje claro. */
async function apiFetch(path: string, init?: RequestInit, okStatuses: number[] = []): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch (err) {
    // Una cancelación (AbortController) no es un error de conexión: la dejamos pasar tal cual.
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(CONNECTION_ERROR, 0);
  }
  if (!res.ok && !okStatuses.includes(res.status)) throw await errorFromResponse(res);
  return res;
}

function headers(sessionId: string, extra?: Record<string, string>) {
  return { "X-Session-ID": sessionId, ...extra };
}

// --- Configuración -------------------------------------------------------------

/** Límites definidos en el backend (tamaño máximo, cantidad de documentos, vencimiento de sesión). */
export async function fetchConfig(): Promise<PublicConfig> {
  return (await apiFetch("/api/config")).json();
}

// --- Documentos ----------------------------------------------------------------

export async function listDocuments(sessionId: string): Promise<DocumentInfo[]> {
  return (await apiFetch("/api/documents", { headers: headers(sessionId) })).json();
}

export async function deleteDocument(sessionId: string, docId: string): Promise<void> {
  // 404 = ya no existe: para el usuario el resultado es el mismo que borrarlo.
  await apiFetch(`/api/documents/${docId}`, { method: "DELETE", headers: headers(sessionId) }, [404]);
}

/** Descarga el PDF como Blob (el endpoint requiere el header de sesión, así que no alcanza con una URL). */
export async function fetchDocumentFile(sessionId: string, docId: string): Promise<Blob> {
  return (await apiFetch(`/api/documents/${docId}/file`, { headers: headers(sessionId) })).blob();
}

/**
 * Sube un PDF. Usa XMLHttpRequest porque fetch no informa el progreso de subida.
 * onProgress recibe 0..1 mientras se sube; al llegar a 1 el backend empieza a procesar.
 */
export function uploadDocument(
  sessionId: string,
  file: File,
  onProgress: (fraction: number) => void,
): Promise<DocumentInfo> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/documents`);
    xhr.setRequestHeader("X-Session-ID", sessionId);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // ignorado
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as DocumentInfo);
      } else {
        const detail = (body as { detail?: unknown } | null)?.detail;
        reject(new ApiError(errorMessage(xhr.status, detail), xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError(CONNECTION_ERROR, 0));

    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

// --- Chat (SSE) ----------------------------------------------------------------

export interface ChatHandlers {
  onSources: (sources: Source[], searchQuery: string) => void;
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

/**
 * Llama a POST /api/chat y procesa el stream SSE.
 * No usamos EventSource porque solo soporta GET; leemos el body con un ReadableStream.
 */
export async function streamChat(
  sessionId: string,
  request: ChatRequest,
  handlers: ChatHandlers,
  signal: AbortSignal,
): Promise<void> {
  const res = await apiFetch("/api/chat", {
    method: "POST",
    headers: headers(sessionId, { "Content-Type": "application/json" }),
    body: JSON.stringify(request),
    signal,
  });
  if (!res.body) throw new ApiError("El servidor no devolvió una respuesta.", res.status);

  const parser = createSSEParser((event, data) => {
    const d = data as Record<string, unknown>;
    switch (event) {
      case "sources":
        handlers.onSources(d.sources as Source[], d.search_query as string);
        break;
      case "token":
        handlers.onToken(d.text as string);
        break;
      case "done":
        handlers.onDone();
        break;
      case "error":
        handlers.onError(d.message as string);
        break;
    }
  });

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(value);
  }
  parser.end();
}
