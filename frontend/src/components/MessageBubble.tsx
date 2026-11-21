import { AlertCircle, Sparkles } from "lucide-react";

import type { Source } from "../api/types";
import type { ChatMessage } from "../hooks/useChat";
import { Markdown } from "./Markdown";
import { SourceList } from "./SourceList";

interface Props {
  message: ChatMessage;
  question: string; // la pregunta del usuario que originó esta respuesta
  onOpenSource: (source: Source) => void;
}

export function MessageBubble({ message, question, onOpenSource }: Props) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-indigo-600 px-4 py-2.5 text-[15px] whitespace-pre-wrap text-white">
          {message.content}
        </div>
      </div>
    );
  }

  const streaming = message.status === "streaming";
  const thinking = streaming && !message.content;

  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-600">
        <Sparkles className="size-4" />
      </div>
      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
        {thinking ? (
          <ThinkingIndicator hasSources={!!message.sources} />
        ) : (
          message.content && (
            <Markdown
              content={message.content}
              sources={message.sources}
              streaming={streaming}
              onOpenSource={onOpenSource}
            />
          )
        )}

        {message.status === "stopped" && <p className="mt-2 text-xs text-slate-400 italic">Respuesta detenida.</p>}

        {message.status === "error" && (
          <div className="mt-2 flex items-start gap-2 rounded-lg bg-red-50 p-2.5 text-sm text-red-700">
            <AlertCircle className="mt-0.5 size-4 shrink-0" />
            {message.error}
          </div>
        )}

        {!streaming && message.sources && (
          <SourceList
            sources={message.sources}
            searchQuery={message.searchQuery}
            question={question}
            onOpenSource={onOpenSource}
          />
        )}
      </div>
    </div>
  );
}

function ThinkingIndicator({ hasSources }: { hasSources: boolean }) {
  return (
    <div className="flex items-center gap-2 py-0.5 text-sm text-slate-500">
      <span className="flex gap-1">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-indigo-400"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </span>
      {hasSources ? "Generando respuesta…" : "Buscando en el documento…"}
    </div>
  );
}
