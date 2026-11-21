"""Guarda los PDFs subidos y sus metadatos en disco: data/uploads/{session_id}/{doc_id}.pdf|.json"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.models import DocumentInfo


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
    (folder / f"{doc_id}.pdf").write_bytes(data)
    (folder / f"{doc_id}.json").write_text(info.model_dump_json(), encoding="utf-8")
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
    for suffix in (".pdf", ".json"):
        path = folder / f"{doc_id}{suffix}"
        if path.exists():
            path.unlink()
            existed = True
    return existed


def delete_session(session_id: str) -> None:
    shutil.rmtree(_session_dir(session_id), ignore_errors=True)
