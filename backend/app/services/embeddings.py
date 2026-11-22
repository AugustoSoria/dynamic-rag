from collections.abc import Callable
from functools import lru_cache

from sentence_transformers import SentenceTransformer

# Cada cuántos fragmentos se informa el progreso. Más chico = barra más fluida, pero cada llamada a
# encode() tiene un costo fijo; 64 da ~25 actualizaciones en un documento de 1500 fragmentos.
PROGRESS_BATCH = 64

from app.config import get_settings


@lru_cache
def _model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model)


def warmup() -> None:
    """Carga el modelo al iniciar la app para que la primera request no sea lenta."""
    _model()


# Los modelos E5 esperan los prefijos "passage: " para documentos y "query: " para preguntas.
def embed_passages(
    texts: list[str], on_progress: Callable[[int, int], None] | None = None
) -> list[list[float]]:
    """Genera los embeddings de a lotes. Si se pasa `on_progress`, se llama con (hechos, total) tras cada lote."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), PROGRESS_BATCH):
        batch = [f"passage: {t}" for t in texts[start : start + PROGRESS_BATCH]]
        vectors.extend(_model().encode(batch, normalize_embeddings=True, batch_size=32, show_progress_bar=False).tolist())
        if on_progress:
            on_progress(len(vectors), len(texts))
    return vectors


def embed_query(text: str) -> list[float]:
    vector = _model().encode(f"query: {text}", normalize_embeddings=True, show_progress_bar=False)
    return vector.tolist()
