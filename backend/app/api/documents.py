from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.api.deps import DocId, SessionId
from app.config import get_settings
from app.models import DocumentInfo, JobStatus
from app.services import document_store, jobs, rag, vector_store
from app.services.pdf_parser import PdfError

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=JobStatus, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(file: UploadFile, session_id: SessionId) -> JobStatus:
    """
    Valida el PDF y lo encola para procesar en segundo plano. Responde 202 con el trabajo:
    el cliente sigue el avance con GET /api/documents/jobs/{doc_id}.
    """
    # El tamaño máximo lo controla UploadSizeLimitMiddleware mientras llega el body (ver app/middleware.py).
    settings = get_settings()

    filename = file.filename or "documento.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Solo se aceptan archivos PDF.")

    # Los que se están procesando también cuentan para el límite.
    in_use = len(document_store.list_documents(session_id)) + jobs.count_active(session_id)
    if in_use >= settings.max_documents_per_session:
        raise HTTPException(
            status_code=409,
            detail=f"Alcanzaste el máximo de {settings.max_documents_per_session} documentos. Eliminá alguno para subir otro.",
        )

    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="El archivo no es un PDF válido.")

    try:
        # La parte rápida (texto + chunks) se hace ya, para devolver los errores de validación al instante.
        prepared = await run_in_threadpool(rag.prepare_pdf, data)
    except PdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return jobs.submit(session_id, filename, data, prepared)


@router.get("/jobs", response_model=list[JobStatus])
def list_active_jobs(session_id: SessionId) -> list[JobStatus]:
    """Trabajos en cola o en proceso (para retomar el progreso si el usuario recarga la página)."""
    return jobs.active_for_session(session_id)


@router.get("/jobs/{doc_id}", response_model=JobStatus)
def get_job(doc_id: DocId, session_id: SessionId) -> JobStatus:
    job = jobs.get(session_id, doc_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado.")
    return job


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
