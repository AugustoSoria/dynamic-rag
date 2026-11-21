import uuid

from app.config import get_settings
from app.models import ChatResponse, DocumentInfo, Source
from app.services import chunker, document_store, embeddings, llm, pdf_parser, vector_store

SYSTEM_PROMPT = """Sos un asistente que responde preguntas sobre documentos PDF subidos por el usuario.

Reglas:
- Respondé ÚNICAMENTE con información de las fuentes que se te dan. No uses conocimiento externo.
- Citá cada afirmación con el número de la fuente entre corchetes, por ejemplo [1] o [2][3].
- Si las fuentes no contienen la respuesta, decí claramente que no encontraste esa información en el documento.
- Respondé en el mismo idioma en que está escrita la pregunta.
- Sé claro y conciso. Usá listas o Markdown cuando ayude a la lectura."""


def ingest_pdf(session_id: str, filename: str, data: bytes) -> DocumentInfo:
    """Pipeline de ingesta: PDF → páginas → chunks → embeddings → Chroma + disco."""
    settings = get_settings()
    pages = pdf_parser.extract_pages(data, max_pages=settings.max_pages)
    chunks = chunker.chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    vectors = embeddings.embed_passages([c.text for c in chunks])

    doc_id = uuid.uuid4().hex
    vector_store.add_chunks(session_id, doc_id, filename, chunks, vectors)
    return document_store.save(session_id, doc_id, filename, data, num_pages=len(pages), num_chunks=len(chunks))


def retrieve(session_id: str, question: str, doc_ids: list[str] | None = None) -> list[Source]:
    settings = get_settings()
    results = vector_store.search(session_id, embeddings.embed_query(question), settings.top_k, doc_ids)
    return [
        Source(index=i, doc_id=r.doc_id, filename=r.filename, page=r.page, text=r.text, score=r.score)
        for i, r in enumerate(results, start=1)
    ]


def _format_sources(sources: list[Source]) -> str:
    return "\n\n".join(f"[{s.index}] ({s.filename}, página {s.page})\n{s.text}" for s in sources)


def answer(session_id: str, question: str, doc_ids: list[str] | None = None) -> ChatResponse:
    sources = retrieve(session_id, question, doc_ids)
    if not sources:
        return ChatResponse(answer="No hay documentos cargados en esta sesión. Subí un PDF para empezar.", sources=[])

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Fuentes:\n\n{_format_sources(sources)}\n\nPregunta: {question}"},
    ]
    return ChatResponse(answer=llm.chat(messages), sources=sources)
