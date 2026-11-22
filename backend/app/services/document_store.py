"""
Guarda los PDFs subidos y sus metadatos en disco:

    data/uploads/{session_id}/{doc_id}.pdf    el archivo original
    data/uploads/{session_id}/{doc_id}.json   metadatos; su existencia es lo que hace "visible" al documento
    data/uploads/{session_id}/.last_activity  su fecha de modificación marca la última actividad de la sesión
"""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.models import DocumentInfo

_ACTIVITY_FILE = ".last_activity"


def _session_dir(session_id: str) -> Path:
    # session_id y doc_id llegan ya validados como UUID desde la capa de API (evita path traversal).
    return get_settings().uploads_dir / session_id


def save(session_id: str, doc_id: str, filename: str, data: bytes, num_pages: int, num_chunks: int) -> DocumentInfo:
    folder = _session_dir(session_id)
    folder.mkdir(parents=True, exist_ok=True)
    info = DocumentInfo(
        doc_id=doc_id,
        filename=filename,
        num_pages=num_pages,
        num_chunks=num_chunks,
        created_at=datetime.now(timezone.utc),
    )
    # Primero el PDF y al final el JSON, escrito de forma atómica: si algo falla a mitad de camino,
    # el documento nunca aparece listado con un archivo faltante.
    (folder / f"{doc_id}.pdf").write_bytes(data)
    tmp = folder / f"{doc_id}.json.tmp"
    tmp.write_text(info.model_dump_json(), encoding="utf-8")
    os.replace(tmp, folder / f"{doc_id}.json")
    touch(session_id)
    return info


def get(session_id: str, doc_id: str) -> DocumentInfo | None:
    meta = _session_dir(session_id) / f"{doc_id}.json"
    if not meta.exists():
        return None
    return DocumentInfo.model_validate(json.loads(meta.read_text(encoding="utf-8")))


def list_documents(session_id: str) -> list[DocumentInfo]:
    folder = _session_dir(session_id)
    if not folder.exists():
        return []
    docs = [DocumentInfo.model_validate_json(p.read_text(encoding="utf-8")) for p in folder.glob("*.json")]
    return sorted(docs, key=lambda d: d.created_at)


def pdf_path(session_id: str, doc_id: str) -> Path | None:
    path = _session_dir(session_id) / f"{doc_id}.pdf"
    return path if path.exists() else None


def delete(session_id: str, doc_id: str) -> bool:
    folder = _session_dir(session_id)
    existed = False
    # El JSON primero: así el documento deja de listarse aunque falle el borrado del PDF.
    for suffix in (".json", ".pdf"):
        path = folder / f"{doc_id}{suffix}"
        if path.exists():
            path.unlink()
            existed = True
    return existed


def delete_session(session_id: str) -> None:
    shutil.rmtree(_session_dir(session_id), ignore_errors=True)


# --- Actividad de sesiones -------------------------------------------------------

def touch(session_id: str) -> None:
    """Registra actividad. Solo para sesiones que tienen documentos (las vacías no ocupan nada)."""
    folder = _session_dir(session_id)
    if folder.exists():
        (folder / _ACTIVITY_FILE).touch()


def list_sessions() -> list[str]:
    root = get_settings().uploads_dir
    return [p.name for p in root.iterdir() if p.is_dir()] if root.exists() else []


def last_activity(session_id: str) -> datetime | None:
    folder = _session_dir(session_id)
    marker = folder / _ACTIVITY_FILE
    # Sin marcador (p. ej. sesiones creadas antes de existir esta función) usamos la fecha de la carpeta.
    path = marker if marker.exists() else folder
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except FileNotFoundError:
        return None
