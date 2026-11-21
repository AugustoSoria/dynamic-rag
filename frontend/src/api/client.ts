import type { ChatRequest, DocumentInfo, Source } from "./types";

const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function errorFromResponse(res: Response): Promise<ApiError> {
  let message = `Error ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // respuesta sin JSON: dejamos el mensaje genérico
  }
  return new ApiError(message, res.status);
}

function headers(sessionId: string, extra?: Record<string, string>) {
  return { "X-Session-ID": sessionId, ...extra };
}

// --- Documentos ----------------------------------------------------------------

export async function listDocuments(sessionId: string): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_URL}/api/documents`, { headers: headers(sessionId) });
  if (!res.ok) throw await errorFromResponse(res);
  return res.json();
}

export async function deleteDocument(sessionId: string, docId: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/documents/${docId}`, { method: "DELETE", headers: headers(sessionId) });
  if (!res.ok && res.status !== 404) throw await errorFromResponse(res);
}

/** Descarga el PDF como Blob (el endpoint requiere el header de sesión, así que no alcanza con una URL). */
export async function fetchDocumentFile(sessionId: string, docId: string): Promise<Blob> {
  const res = await fetch(`${API_URL}/api/documents/${docId}/file`, { headers: headers(sessionId) });
  if (!res.ok) throw await errorFromResponse(res);
  return res.blob();
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
        reject(new ApiError(typeof detail === "string" ? detail : `Error ${xhr.status}`, xhr.status));
      }
    };
    xhr.onerror = () => reject(new ApiError("No se pudo conectar con el servidor.", 0));

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
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: headers(sessionId, { "Content-Type": "application/json" }),
    body: JSON.stringify(request),
    signal,
  });
  if (!res.ok || !res.body) throw await errorFromResponse(res);

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  const dispatch = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) return;
    const data = JSON.parse(dataLines.join("\n"));

    switch (event) {
      case "sources":
        handlers.onSources(data.sources, data.search_query);
        break;
      case "token":
        handlers.onToken(data.text);
        break;
      case "done":
        handlers.onDone();
        break;
      case "error":
        handlers.onError(data.message);
        break;
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");

    // Los eventos SSE se separan con una línea en blanco.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      dispatch(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
    }
  }
  if (buffer.trim()) dispatch(buffer);
}
