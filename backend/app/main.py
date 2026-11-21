from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents
from app.config import get_settings
from app.services import embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    embeddings.warmup()
    yield


settings = get_settings()

app = FastAPI(
    title="Dynamic RAG API",
    description="Subí un PDF y hacé preguntas sobre su contenido.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
