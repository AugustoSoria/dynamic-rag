import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import chat, documents
from app.config import get_settings
from app.middleware import UploadSizeLimitMiddleware
from app.services import embeddings, jobs, sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


async def _cleanup_loop() -> None:
    """Borra periódicamente las sesiones inactivas (PDFs + chunks)."""
    while True:
        try:
            await run_in_threadpool(sessions.cleanup_expired)
        except Exception:
            logger.exception("Falló la limpieza de sesiones")
        await asyncio.sleep(settings.cleanup_interval_minutes * 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    embeddings.warmup()
    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await cleanup_task
    jobs.shutdown()


app = FastAPI(
    title="Dynamic RAG API",
    description="Subí un PDF y hacé preguntas sobre su contenido.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(UploadSizeLimitMiddleware, path="/api/documents", max_mb=settings.max_upload_mb)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    # Los errores inesperados se loguean con el stack completo, pero al cliente no le filtramos detalles internos.
    logger.exception("Error no manejado en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Ocurrió un error interno. Intentá de nuevo."})


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config", tags=["health"])
def public_config() -> dict[str, int]:
    """Límites que el frontend necesita conocer (así no se duplican en dos lugares)."""
    return {
        "max_upload_mb": settings.max_upload_mb,
        "max_pages": settings.max_pages,
        "max_documents_per_session": settings.max_documents_per_session,
        "session_ttl_minutes": settings.session_ttl_minutes,
    }
