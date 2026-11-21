import os
import uuid

import fitz
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import vector_store


@pytest.fixture(scope="session", autouse=True)
def isolated_settings(tmp_path_factory):
    """Datos en una carpeta temporal y una API key falsa: los tests nunca tocan data/ ni llaman a Groq."""
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ["GROQ_API_KEY"] = "test-key"
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


def make_pdf(pages_text: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_textbox(fitz.Rect(50, 50, 550, 800), text)
    data = doc.tobytes()
    doc.close()
    return data
