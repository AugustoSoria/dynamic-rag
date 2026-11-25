from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # LLM (Groq)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    llm_temperature: float = 0.2
    llm_reasoning_effort: Literal["low", "medium", "high"] = "medium"

    # Memoria: cuántos mensajes previos se mandan al LLM
    history_max_messages: int = 6

    # Embeddings
    embedding_model: str = "intfloat/multilingual-e5-small"

    # Almacenamiento
    data_dir: Path = BASE_DIR / "data"

    # Chunking / retrieval
    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 5
    # "hybrid": combina la búsqueda semántica con la de palabras clave (BM25). "vector": solo semántica.
    retrieval_mode: Literal["vector", "hybrid"] = "hybrid"
    # Candidatos que aporta cada búsqueda antes de combinarlas, y constante de la fusión (RRF).
    hybrid_candidates: int = 20
    rrf_k: int = 60

    # Límites de subida
    max_upload_mb: int = 20
    max_pages: int = 300
    max_documents_per_session: int = 3

    # Sesiones: se borran (PDFs + chunks) tras este tiempo sin actividad
    session_ttl_minutes: int = 120
    cleanup_interval_minutes: int = 10

    # Límite de uso por IP (por hora). 0 = sin límite.
    rate_limit_chat_per_hour: int = 30
    rate_limit_uploads_per_hour: int = 10
    # Encabezado con la IP real del usuario cuando hay un proxy/CDN delante (p. ej. CloudFront-Viewer-Address).
    # Vacío = se usa la IP de la conexión. Solo es seguro si al servidor no se puede llegar sin pasar por ese proxy.
    client_ip_header: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
