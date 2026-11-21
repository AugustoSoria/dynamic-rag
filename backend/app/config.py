from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # LLM (Groq)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    llm_temperature: float = 0.2

    # Embeddings
    embedding_model: str = "intfloat/multilingual-e5-small"

    # Almacenamiento
    data_dir: Path = BASE_DIR / "data"

    # Chunking / retrieval
    chunk_size: int = 800
    chunk_overlap: int = 150
    top_k: int = 5

    # Límites de subida
    max_upload_mb: int = 20
    max_pages: int = 300

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
