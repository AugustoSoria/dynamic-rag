import { AlertCircle, Loader2, Upload, X } from "lucide-react";
import { useRef, useState } from "react";

import type { UploadStatus } from "../hooks/useDocuments";

/** Texto y avance (0..1, o null si no se puede medir) para cada etapa de la subida. */
function describe(status: BusyStatus): { fraction: number | null; label: string } {
  switch (status.state) {
    case "uploading":
      return { fraction: status.progress, label: `Subiendo… ${Math.round(status.progress * 100)}%` };
    case "reading":
      return { fraction: null, label: "Leyendo el PDF…" };
    case "queued":
      return {
        fraction: null,
        label:
          status.position > 0
            ? `En cola: ${status.position} ${status.position === 1 ? "documento" : "documentos"} antes que este…`
            : "Por empezar…",
      };
    case "processing": {
      const fraction = status.total ? status.processed / status.total : 0;
      const eta = status.etaSeconds === null ? "" : ` · ${formatEta(status.etaSeconds)}`;
      return {
        fraction,
        label: `Generando embeddings: ${status.processed} de ${status.total} fragmentos (${Math.round(fraction * 100)}%)${eta}`,
      };
    }
  }
}

function formatEta(seconds: number): string {
  if (seconds < 10) return "casi listo";
  if (seconds < 60) return `~${Math.ceil(seconds / 10) * 10} s restantes`;
  const minutes = Math.round(seconds / 60);
  return `~${minutes} min restante${minutes === 1 ? "" : "s"}`;
}

interface Props {
  status: UploadStatus;
  /** Tamaño máximo según el backend (undefined mientras carga la configuración). */
  maxMb?: number;
  /** Si hay un motivo, la zona se deshabilita y lo muestra (p. ej. límite de documentos alcanzado). */
  disabledReason?: string;
  onFile: (file: File) => void;
  onDismissError: () => void;
}

type BusyStatus = Exclude<UploadStatus, { state: "idle" } | { state: "error" }>;

export function UploadZone({ status, maxMb, disabledReason, onFile, onDismissError }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const busy = status.state !== "idle" && status.state !== "error";

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file && !busy) onFile(file);
  };

  if (busy) {
    const { fraction, label } = describe(status);
    return (
      <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4" data-testid="upload-progress">
        <div className="flex items-center gap-2 text-sm font-medium text-indigo-900">
          <Loader2 className="size-4 shrink-0 animate-spin" />
          <span className="truncate">{status.filename}</span>
        </div>
        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-indigo-100"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={fraction === null ? undefined : Math.round(fraction * 100)}
        >
          <div
            className={`h-full rounded-full bg-indigo-500 transition-all duration-500 ${fraction === null ? "w-full animate-pulse" : ""}`}
            style={fraction === null ? undefined : { width: `${Math.max(2, Math.round(fraction * 100))}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-indigo-700">{label}</p>
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        disabled={!!disabledReason}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabledReason) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!disabledReason) handleFiles(e.dataTransfer.files);
        }}
        className={`flex w-full flex-col items-center rounded-xl border-2 border-dashed px-4 py-6 text-center transition disabled:cursor-not-allowed disabled:opacity-60 ${
          dragging
            ? "border-indigo-500 bg-indigo-50"
            : "border-slate-300 enabled:hover:border-indigo-400 enabled:hover:bg-slate-50"
        }`}
      >
        <Upload className={`size-6 ${dragging ? "text-indigo-600" : "text-slate-400"}`} />
        <span className="mt-2 text-sm font-medium text-slate-700">
          {disabledReason ?? "Arrastrá un PDF o hacé clic"}
        </span>
        {!disabledReason && maxMb && <span className="mt-0.5 text-xs text-slate-500">Hasta {maxMb} MB</span>}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = ""; // permite volver a elegir el mismo archivo
        }}
      />

      {status.state === "error" && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span className="flex-1">{status.message}</span>
          <button onClick={onDismissError} className="text-red-400 hover:text-red-700" aria-label="Cerrar">
            <X className="size-4" />
          </button>
        </div>
      )}
    </div>
  );
}
