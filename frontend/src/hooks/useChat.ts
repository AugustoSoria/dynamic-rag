import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { streamChat } from "../api/client";
import type { HistoryMessage, Source } from "../api/types";
import { documentsQueryKey } from "./useDocuments";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  searchQuery?: string;
  status?: "streaming" | "done" | "error" | "stopped";
  error?: string;
}

/** Cuántos mensajes previos mandamos como historial. El backend además recorta a HISTORY_MAX_MESSAGES. */
const HISTORY_LIMIT = 10;

export function useChat(sessionId: string, docIds: string[]) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();

  const updateMessage = (id: string, patch: (m: ChatMessage) => Partial<ChatMessage>) =>
    setMessages((msgs) => msgs.map((m) => (m.id === id ? { ...m, ...patch(m) } : m)));

  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || isStreaming) return;

      // Historial: solo intercambios completos (sin respuestas con error o vacías).
      const history: HistoryMessage[] = messages
        .filter((m) => m.role === "user" || (m.status === "done" && m.content))
        .slice(-HISTORY_LIMIT)
        .map(({ role, content }) => ({ role, content }));

      const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text };
      const assistantId = crypto.randomUUID();
      setMessages((msgs) => [
        ...msgs,
        userMsg,
        { id: assistantId, role: "assistant", content: "", status: "streaming" },
      ]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(
          sessionId,
          { question: text, history, doc_ids: docIds.length ? docIds : null },
          {
            onSources: (sources, searchQuery) => {
              updateMessage(assistantId, () => ({ sources, searchQuery }));
              // Sin fuentes = el backend no tiene documentos para esta sesión (p. ej. venció por inactividad).
              // Refrescamos la lista para que la UI deje de mostrar documentos que ya no existen.
              if (sources.length === 0) queryClient.invalidateQueries({ queryKey: documentsQueryKey(sessionId) });
            },
            onToken: (token) => updateMessage(assistantId, (m) => ({ content: m.content + token })),
            onDone: () => updateMessage(assistantId, () => ({ status: "done" })),
            onError: (message) => updateMessage(assistantId, () => ({ status: "error", error: message })),
          },
          controller.signal,
        );
      } catch (err) {
        if (controller.signal.aborted) {
          updateMessage(assistantId, () => ({ status: "stopped" }));
        } else {
          const message = err instanceof Error ? err.message : "Error desconocido.";
          updateMessage(assistantId, () => ({ status: "error", error: message }));
        }
      } finally {
        // Si el stream se cortó sin evento done/error, lo damos por terminado.
        updateMessage(assistantId, (m) => (m.status === "streaming" ? { status: "done" } : {}));
        abortRef.current = null;
        setIsStreaming(false);
      }
    },
    [sessionId, docIds, messages, isStreaming, queryClient],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
  }, []);

  return { messages, isStreaming, send, stop, clear };
}
