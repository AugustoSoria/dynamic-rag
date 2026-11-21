from datetime import datetime

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    num_pages: int
    num_chunks: int
    created_at: datetime


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
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


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
