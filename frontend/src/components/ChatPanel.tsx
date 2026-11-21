import { FileUp, MessageSquareText, Trash2 } from "lucide-react";
import { useLayoutEffect, useRef } from "react";

import type { useChat } from "../hooks/useChat";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

interface Props {
  chat: ReturnType<typeof useChat>;
  hasDocuments: boolean;
  scopeLabel: string;
  onOpenDocuments: () => void;
}

const EXAMPLE_QUESTIONS = ["¿Cuáles son los puntos principales?", "¿Qué fechas importantes se mencionan?"];

export function ChatPanel({ chat, hasDocuments, scopeLabel, onOpenDocuments }: Props) {
  const { messages, isStreaming, send, stop, clear } = chat;
  const scrollRef = useRef<HTMLDivElement>(null);

  // Mantiene el scroll abajo mientras llegan tokens, salvo que el usuario haya subido a leer.
  // useLayoutEffect: el scroll se ajusta antes de que el navegador pinte, sin saltos visibles.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (nearBottom) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="hidden items-center justify-between border-b border-slate-200 bg-white px-6 py-3 md:flex">
        <span className="text-sm text-slate-500">{scopeLabel}</span>
        {messages.length > 0 && (
          <button
            onClick={clear}
            className="flex items-center gap-1.5 text-sm text-slate-500 transition hover:text-slate-800"
          >
            <Trash2 className="size-4" />
            Limpiar chat
          </button>
        )}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 md:px-6">
          {messages.length === 0 ? (
            <EmptyState hasDocuments={hasDocuments} onAsk={send} onOpenDocuments={onOpenDocuments} />
          ) : (
            messages.map((m, i) => (
              <MessageBubble key={m.id} message={m} question={messages[i - 1]?.content ?? ""} />
            ))
          )}
        </div>
      </div>

      <div className="border-t border-slate-200 bg-slate-50/80 px-4 py-3 backdrop-blur md:px-6">
        <div className="mx-auto max-w-3xl">
          <ChatInput
            disabled={!hasDocuments}
            isStreaming={isStreaming}
            placeholder={hasDocuments ? "Preguntá algo sobre tus documentos…" : "Subí un PDF para empezar"}
            onSend={send}
            onStop={stop}
          />
          <p className="mt-2 text-center text-[11px] text-slate-400">
            Las respuestas se generan solo a partir de tus documentos y pueden contener errores.
          </p>
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  hasDocuments,
  onAsk,
  onOpenDocuments,
}: {
  hasDocuments: boolean;
  onAsk: (q: string) => void;
  onOpenDocuments: () => void;
}) {
  if (!hasDocuments) {
    return (
      <div className="flex flex-col items-center py-20 text-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600">
          <FileUp className="size-7" />
        </div>
        <h2 className="mt-4 text-lg font-semibold text-slate-900">Subí un PDF para empezar</h2>
        <p className="mt-1 max-w-sm text-sm text-slate-500">
          Lo procesamos en segundos y después podés hacerle preguntas. Cada respuesta cita las páginas de donde sale.
        </p>
        <button
          onClick={onOpenDocuments}
          className="mt-5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 md:hidden"
        >
          Subir PDF
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center py-20 text-center">
      <div className="flex size-14 items-center justify-center rounded-2xl bg-indigo-100 text-indigo-600">
        <MessageSquareText className="size-7" />
      </div>
      <h2 className="mt-4 text-lg font-semibold text-slate-900">¿Qué querés saber?</h2>
      <p className="mt-1 text-sm text-slate-500">Hacé una pregunta sobre tus documentos.</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        {EXAMPLE_QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onAsk(q)}
            className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-sm text-slate-600 transition hover:border-indigo-300 hover:text-indigo-700"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
