import { ArrowUp, Square } from "lucide-react";
import { useRef, useState } from "react";

// El textarea crece con su contenido usando CSS `field-sizing: content`.
// En navegadores sin soporte, calculamos la altura a mano al escribir y al enviar.
const supportsFieldSizing = typeof CSS !== "undefined" && CSS.supports("field-sizing", "content");
const MAX_HEIGHT = 200;

function fitHeight(el: HTMLTextAreaElement | null) {
  if (!el || supportsFieldSizing) return;
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
}

interface Props {
  disabled: boolean;
  isStreaming: boolean;
  placeholder: string;
  onSend: (text: string) => void;
  onStop: () => void;
}

export function ChatInput({ disabled, isStreaming, placeholder, onSend, onStop }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    if (!text.trim() || disabled || isStreaming) return;
    onSend(text);
    setText("");
    if (ref.current && !supportsFieldSizing) ref.current.style.height = "auto";
  };

  return (
    <div className="flex items-end gap-2 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100">
      <textarea
        ref={ref}
        name="question"
        rows={1}
        value={text}
        disabled={disabled}
        placeholder={placeholder}
        maxLength={2000}
        onChange={(e) => {
          setText(e.target.value);
          fitHeight(e.target);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            submit();
          }
        }}
        className="max-h-[200px] flex-1 resize-none [field-sizing:content] bg-transparent px-2 py-1.5 text-[15px] outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
      />
      {isStreaming ? (
        <button
          onClick={onStop}
          className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-white hover:bg-slate-700"
          aria-label="Detener respuesta"
        >
          <Square className="size-3.5 fill-current" />
        </button>
      ) : (
        <button
          onClick={submit}
          disabled={disabled || !text.trim()}
          className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white transition hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400"
          aria-label="Enviar"
        >
          <ArrowUp className="size-5" />
        </button>
      )}
    </div>
  );
}
