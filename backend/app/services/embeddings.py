from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings


@lru_cache
def _model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model)


def warmup() -> None:
    """Carga el modelo al iniciar la app para que la primera request no sea lenta."""
    _model()


# Los modelos E5 esperan los prefijos "passage: " para documentos y "query: " para preguntas.
def embed_passages(texts: list[str]) -> list[list[float]]:
    vectors = _model().encode(
        [f"passage: {t}" for t in texts], normalize_embeddings=True, batch_size=32, show_progress_bar=False
    )
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    vector = _model().encode(f"query: {text}", normalize_embeddings=True, show_progress_bar=False)
    return vector.tolist()
