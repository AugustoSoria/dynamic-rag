from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.api.deps import DocId, SessionId
from app.config import get_settings
from app.models import DocumentInfo
from app.services import document_store, rag, vector_store
from app.services.pdf_parser import PdfError

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=DocumentInfo, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile, session_id: SessionId) -> DocumentInfo:
    # El tamaño máximo lo controla UploadSizeLimitMiddleware mientras llega el body (ver app/middleware.py).
    settings = get_settings()

    filename = file.filename or "documento.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Solo se aceptan archivos PDF.")

    if len(document_store.list_documents(session_id)) >= settings.max_documents_per_session:
        raise HTTPException(
            status_code=409,
            detail=f"Alcanzaste el máximo de {settings.max_documents_per_session} documentos. Eliminá alguno para subir otro.",
        )

    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="El archivo no es un PDF válido.")

    try:
        # Parsing + embeddings son CPU-bound: los corremos fuera del event loop.
        return await run_in_threadpool(rag.ingest_pdf, session_id, filename, data)
    except PdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=list[DocumentInfo])
def list_documents(session_id: SessionId) -> list[DocumentInfo]:
    return document_store.list_documents(session_id)


@router.get("/{doc_id}/file", response_class=FileResponse)
def get_document_file(doc_id: DocId, session_id: SessionId) -> FileResponse:
    info = document_store.get(session_id, doc_id)
    path = document_store.pdf_path(session_id, doc_id)
    if info is None or path is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return FileResponse(path, media_type="application/pdf", filename=info.filename, content_disposition_type="inline")


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: DocId, session_id: SessionId) -> None:
    if document_store.get(session_id, doc_id) is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    # Primero los chunks: si después falla el borrado de archivos, el documento sigue listado y se puede
    # reintentar. Al revés, quedarían chunks de un documento invisible apareciendo como fuentes en el chat.
    vector_store.delete_document(session_id, doc_id)
    document_store.delete(session_id, doc_id)
