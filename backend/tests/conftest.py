import os
import time
import uuid

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import vector_store


@pytest.fixture(scope="session", autouse=True)
def isolated_settings(tmp_path_factory):
    """Datos en una carpeta temporal y una API key falsa: los tests nunca tocan data/ ni llaman a Groq."""
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ["GROQ_API_KEY"] = "test-key"
    # Límites bajos para poder probarlos con archivos chicos.
    os.environ["MAX_UPLOAD_MB"] = "1"
    os.environ["MAX_DOCUMENTS_PER_SESSION"] = "3"
    # Sin límite de uso por IP (todos los tests salen de la misma IP); test_rate_limit lo activa.
    os.environ["RATE_LIMIT_CHAT_PER_HOUR"] = "0"
    os.environ["RATE_LIMIT_UPLOADS_PER_HOUR"] = "0"
    get_settings.cache_clear()
    vector_store._collection.cache_clear()
    yield


@pytest.fixture(scope="session")
def client(isolated_settings):
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_headers():
    return {"X-Session-ID": str(uuid.uuid4())}


def upload_pdf(client, headers, pages_text=("Contenido de prueba.",), filename="doc.pdf", data: bytes | None = None):
    """Sube un PDF y, si fue aceptado (202), espera a que termine de procesarse. Devuelve la respuesta del POST."""
    pdf = data if data is not None else make_pdf(list(pages_text))
    r = client.post("/api/documents", headers=headers, files={"file": (filename, pdf, "application/pdf")})
    if r.status_code == 202:
        job = wait_for_job(client, headers, r.json()["doc_id"])
        assert job["status"] == "ready", job
    return r


def wait_for_job(client, headers, doc_id: str, timeout: float = 60) -> dict:
    """Consulta el trabajo hasta que termine (ready o error)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/documents/jobs/{doc_id}", headers=headers).json()
        if job["status"] in ("ready", "error"):
            return job
        time.sleep(0.05)
    raise TimeoutError(f"El trabajo {doc_id} no terminó en {timeout}s")


def make_pdf(pages_text: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text)
    data = doc.tobytes()
    doc.close()
    return data
