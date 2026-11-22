from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    num_pages: int
    num_chunks: int
    created_at: datetime


class JobStatus(BaseModel):
    """Estado del procesamiento en segundo plano de un PDF subido."""

    doc_id: str
    filename: str
    status: Literal["queued", "processing", "ready", "error"]
    processed: int = Field(description="Fragmentos con embeddings ya generados.")
    total: int = Field(description="Total de fragmentos del documento.")
    queue_position: int = Field(default=0, description="Trabajos por delante en la cola (0 = procesándose o terminado).")
    elapsed_seconds: float = Field(default=0, description="Segundos desde que empezó a procesarse (para estimar lo que falta).")
    error: str | None = None
    document: DocumentInfo | None = Field(default=None, description="El documento, cuando status es 'ready'.")


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=50,
        description="Mensajes previos de la conversación (el cliente guarda el historial; el backend es stateless).",
    )
    doc_ids: list[str] | None = Field(
        default=None, description="Restringe la búsqueda a estos documentos. Si es null, usa todos los de la sesión."
    )


class Source(BaseModel):
    index: int
    doc_id: str
    filename: str
    page: int
    text: str
    score: float
