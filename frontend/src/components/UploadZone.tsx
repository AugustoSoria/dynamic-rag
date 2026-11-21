import { AlertCircle, Loader2, Upload, X } from "lucide-react";
import { useRef, useState } from "react";

import { MAX_UPLOAD_MB, type UploadStatus } from "../hooks/useDocuments";

interface Props {
  status: UploadStatus;
  onFile: (file: File) => void;
  onDismissError: () => void;
}

export function UploadZone({ status, onFile, onDismissError }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const busy = status.state === "uploading" || status.state === "processing";

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file && !busy) onFile(file);
  };

  if (busy) {
    const uploading = status.state === "uploading";
    return (
      <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-indigo-900">
          <Loader2 className="size-4 shrink-0 animate-spin" />
          <span className="truncate">{status.filename}</span>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-indigo-100">
          <div
            className={`h-full rounded-full bg-indigo-500 transition-all ${uploading ? "" : "w-full animate-pulse"}`}
            style={uploading ? { width: `${Math.round(status.progress * 100)}%` } : undefined}
          />
        </div>
        <p className="mt-2 text-xs text-indigo-700">
          {uploading ? `Subiendo… ${Math.round(status.progress * 100)}%` : "Extrayendo texto y generando embeddings…"}
        </p>
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`flex w-full flex-col items-center rounded-xl border-2 border-dashed px-4 py-6 text-center transition ${
          dragging ? "border-indigo-500 bg-indigo-50" : "border-slate-300 hover:border-indigo-400 hover:bg-slate-50"
        }`}
      >
        <Upload className={`size-6 ${dragging ? "text-indigo-600" : "text-slate-400"}`} />
        <span className="mt-2 text-sm font-medium text-slate-700">Arrastrá un PDF o hacé clic</span>
        <span className="mt-0.5 text-xs text-slate-500">Hasta {MAX_UPLOAD_MB} MB</span>
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
