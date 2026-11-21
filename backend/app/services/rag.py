import logging
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.config import get_settings
from app.models import DocumentInfo, HistoryMessage, Source
from app.services import chunker, document_store, embeddings, llm, pdf_parser, vector_store

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sos un asistente que responde preguntas sobre documentos PDF subidos por el usuario.

Reglas:
- Respondé ÚNICAMENTE con información de las fuentes que se te dan en el último mensaje. No uses conocimiento externo.
- Citá cada afirmación con el número de la fuente entre corchetes, por ejemplo [1] o [2][3]. Usá solo números de fuentes que existan.
- Si las fuentes no contienen la respuesta, decí claramente que no encontraste esa información en el documento. No inventes.
- Podés usar la conversación previa para entender a qué se refiere el usuario, pero los datos tienen que salir de las fuentes.
- Respondé en el mismo idioma en que está escrita la pregunta.
- Sé claro y conciso. Usá listas o Markdown cuando ayude a la lectura."""

REWRITE_PROMPT = """Tu tarea es reescribir la última pregunta del usuario para que se entienda sola, sin necesidad de leer la conversación previa. Se va a usar para buscar en un documento.

- Reemplazá pronombres y referencias ("eso", "él", "ese año", "y después?") por lo que corresponda según la conversación.
- Si la pregunta ya se entiende sola, devolvela igual.
- No la respondas. Mantené el idioma original.
- Devolvé SOLAMENTE la pregunta reescrita, sin comillas ni explicaciones."""

NO_DOCUMENTS_MESSAGE = "No hay documentos cargados en esta sesión. Subí un PDF para empezar."

_CITATION_RE = re.compile(r"\[\d+\]")


@dataclass
class Event:
    """Evento del stream de chat. La capa de API lo serializa como SSE."""

    name: str
    data: dict[str, Any]


# --- Ingesta -----------------------------------------------------------------

def ingest_pdf(session_id: str, filename: str, data: bytes) -> DocumentInfo:
    """Pipeline de ingesta: PDF → páginas → chunks → embeddings → Chroma + disco."""
    settings = get_settings()
    pages = pdf_parser.extract_pages(data, max_pages=settings.max_pages)
    chunks = chunker.chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    vectors = embeddings.embed_passages([c.text for c in chunks])

    doc_id = uuid.uuid4().hex
    vector_store.add_chunks(session_id, doc_id, filename, chunks, vectors)
    return document_store.save(session_id, doc_id, filename, data, num_pages=len(pages), num_chunks=len(chunks))


# --- Retrieval ---------------------------------------------------------------

def retrieve(session_id: str, question: str, doc_ids: list[str] | None = None) -> list[Source]:
    settings = get_settings()
    results = vector_store.search(session_id, embeddings.embed_query(question), settings.top_k, doc_ids)
    return [
        Source(index=i, doc_id=r.doc_id, filename=r.filename, page=r.page, text=r.text, score=r.score)
        for i, r in enumerate(results, start=1)
    ]


# --- Memoria -----------------------------------------------------------------

def _recent_history(history: list[HistoryMessage]) -> list[HistoryMessage]:
    return history[-get_settings().history_max_messages :] if history else []


def _history_as_messages(history: list[HistoryMessage]) -> list[dict[str, str]]:
    # Las citas [n] de respuestas anteriores apuntan a otras fuentes: las sacamos para no confundir al modelo.
    return [
        {"role": m.role, "content": _CITATION_RE.sub("", m.content) if m.role == "assistant" else m.content}
        for m in _recent_history(history)
    ]


def rewrite_question(question: str, history: list[HistoryMessage]) -> str:
    """Convierte una pregunta de seguimiento ("¿y cuándo pasó eso?") en una pregunta autónoma para el retrieval."""
    if not history:
        return question

    transcript = "\n".join(
        f"{'Usuario' if m.role == 'user' else 'Asistente'}: {_CITATION_RE.sub('', m.content)[:1000]}"
        for m in _recent_history(history)
    )
    messages = [
        {"role": "system", "content": REWRITE_PROMPT},
        {"role": "user", "content": f"Conversación:\n{transcript}\n\nÚltima pregunta: {question}"},
    ]
    try:
        rewritten = llm.complete(messages, reasoning_effort="low").strip().strip('"«»')
    except Exception:
        # Si falla la reescritura no cortamos la respuesta: buscamos con la pregunta original.
        logger.exception("Falló la reescritura de la pregunta; se usa la original")
        return question
    return rewritten or question


# --- Respuesta ---------------------------------------------------------------

def _format_sources(sources: list[Source]) -> str:
    return "\n\n".join(f"[{s.index}] ({s.filename}, página {s.page})\n{s.text}" for s in sources)


def build_messages(question: str, sources: list[Source], history: list[HistoryMessage]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *_history_as_messages(history),
        {"role": "user", "content": f"Fuentes:\n\n{_format_sources(sources)}\n\nPregunta: {question}"},
    ]


def stream_answer(
    session_id: str, question: str, history: list[HistoryMessage], doc_ids: list[str] | None = None
) -> Iterator[Event]:
    """
    Flujo completo de una pregunta:
      1. reescribe la pregunta usando el historial
      2. busca las fuentes con la pregunta reescrita
      3. emite las fuentes (para que el frontend las muestre ya)
      4. emite la respuesta del LLM token a token
    """
    search_query = rewrite_question(question, history)
    sources = retrieve(session_id, search_query, doc_ids)

    yield Event("sources", {"search_query": search_query, "sources": [s.model_dump() for s in sources]})

    if not sources:
        yield Event("token", {"text": NO_DOCUMENTS_MESSAGE})
        yield Event("done", {})
        return

    for text in llm.stream(build_messages(question, sources, history)):
        yield Event("token", {"text": text})
    yield Event("done", {})
