import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.config import get_settings
from app.services import document_store
from app.services.rate_limit import format_wait, limiter


def get_session_id(
    x_session_id: Annotated[str, Header(description="UUID de sesión generado por el cliente")],
) -> str:
    """
    Valida el header X-Session-ID (se usa como nombre de carpeta, así que debe ser un UUID estricto)
    y registra actividad, para que la limpieza automática no borre sesiones en uso.
    """
    try:
        session_id = str(uuid.UUID(x_session_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Session-ID debe ser un UUID válido.")
    document_store.touch(session_id)
    return session_id


def normalize_doc_id(doc_id: str) -> str:
    """Los doc_id son UUID en hex. Cualquier otro valor se trata como inexistente."""
    try:
        return uuid.UUID(hex=doc_id).hex
    except ValueError:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")


def _rate_limit(action: str, setting: str):
    """Dependencia que limita cuántas veces por hora una misma IP puede hacer `action`."""

    def check(request: Request) -> None:
        limit = getattr(get_settings(), setting)
        if limit <= 0:
            return
        # Detrás del proxy (Caddy), uvicorn toma la IP real de X-Forwarded-For (--proxy-headers).
        ip = request.client.host if request.client else "desconocida"
        wait = limiter.hit(f"{action}:{ip}", limit, 3600)
        if wait is not None:
            raise HTTPException(
                status_code=429,
                detail=f"Alcanzaste el límite de uso de esta demo. Probá de nuevo en {format_wait(wait)}.",
                headers={"Retry-After": str(int(wait) + 1)},
            )

    return Depends(check)


ChatRateLimit = _rate_limit("chat", "rate_limit_chat_per_hour")
UploadRateLimit = _rate_limit("upload", "rate_limit_uploads_per_hour")

SessionId = Annotated[str, Depends(get_session_id)]
DocId = Annotated[str, Depends(normalize_doc_id)]
