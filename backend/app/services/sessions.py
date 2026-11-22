"""Ciclo de vida de las sesiones anónimas: borrado y limpieza de las inactivas."""

import logging
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services import document_store, vector_store

logger = logging.getLogger(__name__)


def delete_session(session_id: str) -> None:
    # Primero los chunks y después los archivos: si se corta a mitad de camino, la carpeta sigue
    # existiendo y la próxima limpieza lo reintenta. Al revés quedarían chunks huérfanos para siempre.
    vector_store.delete_session(session_id)
    document_store.delete_session(session_id)


def cleanup_expired(now: datetime | None = None) -> list[str]:
    """Borra las sesiones sin actividad hace más de SESSION_TTL_MINUTES. Devuelve los ids borrados."""
    now = now or datetime.now(timezone.utc)
    limit = now - timedelta(minutes=get_settings().session_ttl_minutes)

    deleted = []
    for session_id in document_store.list_sessions():
        last = document_store.last_activity(session_id)
        if last is not None and last < limit:
            try:
                delete_session(session_id)
                deleted.append(session_id)
            except Exception:
                logger.exception("No se pudo borrar la sesión %s; se reintenta en la próxima limpieza", session_id)

    if deleted:
        logger.info("Limpieza: %d sesiones inactivas eliminadas", len(deleted))
    return deleted
