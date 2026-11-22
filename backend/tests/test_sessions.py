import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.services import document_store, embeddings, rag, sessions, vector_store
from tests.conftest import make_pdf, upload_pdf


def chunks_in_store(session_id: str) -> int:
    return len(vector_store.search(session_id, embeddings.embed_query("contenido"), k=10))


def make_inactive(session_id: str, hours: float) -> None:
    """Simula que la última actividad de la sesión fue hace `hours` horas."""
    marker = get_settings().uploads_dir / session_id / ".last_activity"
    old = time.time() - hours * 3600
    os.utime(marker, (old, old))


def test_requests_register_activity(client, session_headers):
    upload_pdf(client, session_headers)
    session_id = session_headers["X-Session-ID"]
    make_inactive(session_id, hours=5)

    client.get("/api/documents", headers=session_headers)

    last = document_store.last_activity(session_id)
    assert datetime.now(timezone.utc) - last < timedelta(minutes=1)


def test_cleanup_deletes_only_inactive_sessions(client):
    old = {"X-Session-ID": str(uuid.uuid4())}
    active = {"X-Session-ID": str(uuid.uuid4())}
    upload_pdf(client, old, ["Contenido viejo"])
    upload_pdf(client, active, ["Contenido nuevo"])
    make_inactive(old["X-Session-ID"], hours=3)  # TTL por defecto: 2 h

    deleted = sessions.cleanup_expired()

    assert old["X-Session-ID"] in deleted
    assert active["X-Session-ID"] not in deleted
    # La sesión vieja desaparece de disco y de Chroma; la activa queda intacta.
    assert client.get("/api/documents", headers=old).json() == []
    assert chunks_in_store(old["X-Session-ID"]) == 0
    assert len(client.get("/api/documents", headers=active).json()) == 1
    assert chunks_in_store(active["X-Session-ID"]) == 1


def test_ingest_rolls_back_chunks_if_saving_fails(monkeypatch):
    session_id = str(uuid.uuid4())

    def broken_save(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(document_store, "save", broken_save)
    with pytest.raises(OSError):
        rag.ingest_pdf(session_id, "doc.pdf", make_pdf(["Contenido que no debería quedar"]))

    assert chunks_in_store(session_id) == 0


def test_delete_removes_chunks(client, session_headers):
    doc_id = upload_pdf(client, session_headers).json()["doc_id"]
    session_id = session_headers["X-Session-ID"]
    assert chunks_in_store(session_id) == 1

    client.delete(f"/api/documents/{doc_id}", headers=session_headers)
    assert chunks_in_store(session_id) == 0
