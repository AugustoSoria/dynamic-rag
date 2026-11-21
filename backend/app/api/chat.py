import uuid

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.api.deps import SessionId
from app.models import ChatRequest, ChatResponse
from app.services import rag
from app.services.llm import LLMNotConfiguredError

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, session_id: SessionId) -> ChatResponse:
    doc_ids = request.doc_ids
    if doc_ids:
        try:
            doc_ids = [uuid.UUID(hex=d).hex for d in doc_ids]
        except ValueError:
            raise HTTPException(status_code=422, detail="doc_ids contiene un id inválido.")

    try:
        return await run_in_threadpool(rag.answer, session_id, request.question, doc_ids)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
