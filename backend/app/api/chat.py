import json
import logging
import uuid
from collections.abc import Iterator

import groq
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import ChatRateLimit, SessionId
from app.models import ChatRequest
from app.services import llm, rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


def _sse(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _error_message(exc: Exception) -> str:
    if isinstance(exc, groq.RateLimitError):
        return "Se alcanzó el límite de uso del modelo. Esperá unos segundos y volvé a intentar."
    if isinstance(exc, groq.APIConnectionError):
        return "No se pudo conectar con el modelo. Intentá de nuevo."
    return "Ocurrió un error generando la respuesta."


def _event_stream(session_id: str, request: ChatRequest, doc_ids: list[str] | None) -> Iterator[str]:
    # Una vez que empezó el stream ya no se puede cambiar el status HTTP:
    # los errores se informan como un evento `error`.
    try:
        for event in rag.stream_answer(session_id, request.question, request.history, doc_ids):
            yield _sse(event.name, event.data)
    except Exception as exc:
        logger.exception("Error durante el stream de chat")
        yield _sse("error", {"message": _error_message(exc)})


@router.post(
    "/chat",
    response_class=StreamingResponse,
    dependencies=[ChatRateLimit],
    responses={200: {"content": {"text/event-stream": {}}, "description": "Stream SSE: sources → token* → done | error"}},
)
def chat(request: ChatRequest, session_id: SessionId) -> StreamingResponse:
    doc_ids = request.doc_ids
    if doc_ids:
        try:
            doc_ids = [uuid.UUID(hex=d).hex for d in doc_ids]
        except ValueError:
            raise HTTPException(status_code=422, detail="doc_ids contiene un id inválido.")

    # Validamos antes de abrir el stream para poder devolver un status HTTP real.
    try:
        llm.ensure_configured()
    except llm.LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return StreamingResponse(
        _event_stream(session_id, request, doc_ids),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # evita buffering en proxies
    )
