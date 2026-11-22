import uuid

from tests.conftest import make_pdf, upload_pdf


def test_upload_list_file_delete(client, session_headers):
    r = upload_pdf(client, session_headers, ["Página uno", "", "Página tres"], filename="informe.pdf")
    assert r.status_code == 201
    doc = r.json()
    assert doc["filename"] == "informe.pdf"
    assert doc["num_pages"] == 3  # incluye la página en blanco
    assert doc["num_chunks"] == 2

    listed = client.get("/api/documents", headers=session_headers).json()
    assert [d["doc_id"] for d in listed] == [doc["doc_id"]]

    file = client.get(f"/api/documents/{doc['doc_id']}/file", headers=session_headers)
    assert file.status_code == 200
    assert file.headers["content-type"] == "application/pdf"
    assert file.content.startswith(b"%PDF")

    assert client.delete(f"/api/documents/{doc['doc_id']}", headers=session_headers).status_code == 204
    assert client.get("/api/documents", headers=session_headers).json() == []
    assert client.delete(f"/api/documents/{doc['doc_id']}", headers=session_headers).status_code == 404


def test_sessions_are_isolated(client, session_headers):
    doc_id = upload_pdf(client, session_headers).json()["doc_id"]
    other = {"X-Session-ID": str(uuid.uuid4())}

    assert client.get("/api/documents", headers=other).json() == []
    assert client.get(f"/api/documents/{doc_id}/file", headers=other).status_code == 404
    assert client.delete(f"/api/documents/{doc_id}", headers=other).status_code == 404
    # El documento sigue intacto para su dueño.
    assert len(client.get("/api/documents", headers=session_headers).json()) == 1


def test_invalid_session_header(client):
    assert client.get("/api/documents", headers={"X-Session-ID": "../../etc"}).status_code == 400
    assert client.get("/api/documents").status_code == 422  # header faltante


def test_invalid_doc_id_is_404(client, session_headers):
    assert client.get("/api/documents/../../secret/file", headers=session_headers).status_code == 404
    assert client.delete("/api/documents/no-es-un-uuid", headers=session_headers).status_code == 404


def test_rejects_non_pdf(client, session_headers):
    r = client.post("/api/documents", headers=session_headers, files={"file": ("notas.txt", b"hola", "text/plain")})
    assert r.status_code == 415

    # Extensión .pdf pero contenido que no es PDF.
    r = client.post("/api/documents", headers=session_headers, files={"file": ("falso.pdf", b"hola", "application/pdf")})
    assert r.status_code == 415


def test_rejects_pdf_without_text(client, session_headers):
    r = client.post(
        "/api/documents", headers=session_headers, files={"file": ("escaneado.pdf", make_pdf(["", ""]), "application/pdf")}
    )
    assert r.status_code == 422
    assert "texto extraíble" in r.json()["detail"]


def test_max_documents_per_session(client, session_headers):
    for i in range(3):  # MAX_DOCUMENTS_PER_SESSION=3 en conftest
        assert upload_pdf(client, session_headers, filename=f"{i}.pdf").status_code == 201
    r = upload_pdf(client, session_headers, filename="extra.pdf")
    assert r.status_code == 409
    assert "máximo de 3" in r.json()["detail"]


# --- Límite de tamaño (MAX_UPLOAD_MB=1 en conftest) --------------------------------

TWO_MB = b"%PDF" + b"0" * (2 * 1024 * 1024)


def test_too_large_with_content_length(client, session_headers):
    r = client.post("/api/documents", headers=session_headers, files={"file": ("grande.pdf", TWO_MB, "application/pdf")})
    assert r.status_code == 413
    assert r.json()["detail"] == "El archivo supera el máximo de 1 MB."


def test_too_large_chunked_without_content_length(client, session_headers):
    """Sin Content-Length el middleware cuenta los bytes a medida que llegan y corta igual."""
    boundary = "limite"
    head = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"grande.pdf\"\r\n"
        "Content-Type: application/pdf\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()

    def body():  # un generador hace que httpx use transferencia por partes (sin Content-Length)
        yield head
        for i in range(0, len(TWO_MB), 64 * 1024):
            yield TWO_MB[i : i + 64 * 1024]
        yield tail

    r = client.post(
        "/api/documents",
        headers={**session_headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        content=body(),
    )
    assert r.status_code == 413
    assert "máximo de 1 MB" in r.json()["detail"]


def test_public_config(client):
    assert client.get("/api/config").json() == {
        "max_upload_mb": 1,
        "max_pages": 300,
        "max_documents_per_session": 3,
        "session_ttl_minutes": 120,
    }
