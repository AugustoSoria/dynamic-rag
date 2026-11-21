from dataclasses import dataclass
from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection

from app.config import get_settings
from app.services.chunker import Chunk

COLLECTION_NAME = "chunks"


@dataclass
class RetrievedChunk:
    doc_id: str
    filename: str
    page: int
    text: str
    score: float  # similitud coseno: 1 = idéntico


@lru_cache
def _collection() -> Collection:
    settings = get_settings()
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    # Pasamos los embeddings nosotros, así que no usamos la embedding function de Chroma.
    return client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}, embedding_function=None
    )


def add_chunks(
    session_id: str, doc_id: str, filename: str, chunks: list[Chunk], embeddings: list[list[float]]
) -> None:
    _collection().add(
        ids=[f"{doc_id}:{c.chunk_index}" for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[
            {"session_id": session_id, "doc_id": doc_id, "filename": filename, "page": c.page} for c in chunks
        ],
    )


def _where(session_id: str, doc_ids: list[str] | None) -> dict:
    if not doc_ids:
        return {"session_id": session_id}
    doc_filter = {"doc_id": doc_ids[0]} if len(doc_ids) == 1 else {"doc_id": {"$in": doc_ids}}
    return {"$and": [{"session_id": session_id}, doc_filter]}


def search(
    session_id: str, query_embedding: list[float], k: int, doc_ids: list[str] | None = None
) -> list[RetrievedChunk]:
    result = _collection().query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=_where(session_id, doc_ids),
        include=["documents", "metadatas", "distances"],
    )
    return [
        RetrievedChunk(
            doc_id=meta["doc_id"],
            filename=meta["filename"],
            page=meta["page"],
            text=text,
            score=round(1 - dist, 4),
        )
        for text, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0])
    ]


def delete_document(session_id: str, doc_id: str) -> None:
    _collection().delete(where=_where(session_id, [doc_id]))


def delete_session(session_id: str) -> None:
    _collection().delete(where={"session_id": session_id})
