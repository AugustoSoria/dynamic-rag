"""Procesamiento en segundo plano: progreso, cola, visibilidad y errores."""

import threading
import time
import uuid

import pytest

from app.services import embeddings, vector_store
from tests.conftest import make_pdf, wait_for_job

LONG_PDF = make_pdf([" ".join(f"Oración {p}-{i} del documento de prueba." for i in range(60)) for p in range(4)])


def post(client, headers, filename="doc.pdf", data=LONG_PDF):
    r = client.post("/api/documents", headers=headers, files={"file": (filename, data, "application/pdf")})
    assert r.status_code == 202, r.text
    return r.json()


def wait_until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError


@pytest.fixture
def gated_embeddings(monkeypatch):
    """Frena la generación de embeddings después del primer lote hasta que el test lo libere."""
    gate = threading.Event()
    real = embeddings.embed_passages

    def gated(texts, on_progress=None):
        if on_progress:
            on_progress(1, len(texts))
        gate.wait(10)
        return real(texts, on_progress=on_progress)

    monkeypatch.setattr(embeddings, "embed_passages", gated)
    yield gate
    gate.set()  # por si el test falla antes de liberarlo


def test_upload_responds_immediately_and_reports_progress(client, session_headers, gated_embeddings):
    job = post(client, session_headers, "largo.pdf")
    assert job["status"] in ("queued", "processing")
    assert job["total"] > 1
    assert job["document"] is None

    get_job = lambda: client.get(f"/api/documents/jobs/{job['doc_id']}", headers=session_headers).json()  # noqa: E731
    wait_until(lambda: get_job()["processed"] == 1)
    assert get_job()["status"] == "processing"

    # Mientras se procesa, el documento no aparece ni en la lista ni en las búsquedas.
    assert client.get("/api/documents", headers=session_headers).json() == []
    q = embeddings.embed_query("oración del documento")
    assert vector_store.search(session_headers["X-Session-ID"], q, k=5) == []

    gated_embeddings.set()
    done = wait_for_job(client, session_headers, job["doc_id"])
    assert done["status"] == "ready"
    assert done["processed"] == done["total"]
    assert done["document"]["num_chunks"] == done["total"]
    assert [d["doc_id"] for d in client.get("/api/documents", headers=session_headers).json()] == [job["doc_id"]]


def test_second_upload_waits_in_queue(client, session_headers, gated_embeddings):
    first = post(client, session_headers, "primero.pdf")
    wait_until(
        lambda: client.get(f"/api/documents/jobs/{first['doc_id']}", headers=session_headers).json()["status"]
        == "processing"
    )
    second = post(client, session_headers, "segundo.pdf")
    assert second["status"] == "queued"
    assert second["queue_position"] == 1

    active = client.get("/api/documents/jobs", headers=session_headers).json()
    assert [j["filename"] for j in active] == ["primero.pdf", "segundo.pdf"]

    gated_embeddings.set()
    assert wait_for_job(client, session_headers, first["doc_id"])["status"] == "ready"
    assert wait_for_job(client, session_headers, second["doc_id"])["status"] == "ready"
    assert client.get("/api/documents/jobs", headers=session_headers).json() == []


def test_jobs_in_progress_count_for_the_limit(client, session_headers, gated_embeddings):
    for i in range(3):  # MAX_DOCUMENTS_PER_SESSION=3 en conftest
        post(client, session_headers, f"{i}.pdf")
    r = client.post("/api/documents", headers=session_headers, files={"file": ("extra.pdf", LONG_PDF, "application/pdf")})
    assert r.status_code == 409
    gated_embeddings.set()
    for job in client.get("/api/documents/jobs", headers=session_headers).json():
        wait_for_job(client, session_headers, job["doc_id"])


def test_processing_error_is_reported_and_leaves_nothing(client, session_headers, monkeypatch):
    def broken_add(*args, **kwargs):
        raise RuntimeError("Chroma caído")

    monkeypatch.setattr(vector_store, "add_chunks", broken_add)
    job = post(client, session_headers)
    done = wait_for_job(client, session_headers, job["doc_id"])

    assert done["status"] == "error"
    assert done["error"] == "No se pudo procesar el documento. Intentá subirlo de nuevo."  # sin detalles internos
    assert client.get("/api/documents", headers=session_headers).json() == []


def test_jobs_are_isolated_by_session(client, session_headers):
    job = post(client, session_headers)
    other = {"X-Session-ID": str(uuid.uuid4())}
    assert client.get(f"/api/documents/jobs/{job['doc_id']}", headers=other).status_code == 404
    assert client.get("/api/documents/jobs", headers=other).json() == []
    wait_for_job(client, session_headers, job["doc_id"])


def test_validation_errors_are_still_immediate(client, session_headers):
    """Los errores de validación no esperan al procesamiento: llegan en la respuesta de la subida."""
    r = client.post(
        "/api/documents", headers=session_headers, files={"file": ("vacio.pdf", make_pdf(["", ""]), "application/pdf")}
    )
    assert r.status_code == 422
    assert client.get("/api/documents/jobs", headers=session_headers).json() == []
