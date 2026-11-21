from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    num_pages: int
    num_chunks: int
    created_at: datetime


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
