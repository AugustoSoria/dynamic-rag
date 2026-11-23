"""
Procesamiento de PDFs en segundo plano.

La subida responde enseguida con un trabajo (`JobStatus`) y los embeddings se generan en un hilo
aparte. El cliente consulta el estado para mostrar el avance real ("640 de 1577 fragmentos").

Decisiones:
- Un solo hilo de trabajo: generar embeddings usa toda la CPU disponible (el servidor de
  producción, una EC2 t3.small, tiene 2 vCPU). Procesar dos PDFs a la vez no termina antes ninguno; los demás esperan
  en cola y el cliente ve su posición.
- El registro vive en memoria: alcanza para un solo proceso. Si el servidor se reinicia, los
  trabajos en curso se pierden (el documento nunca llegó a guardarse, así que no queda nada a medias).
"""

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from app.models import DocumentInfo, JobStatus
from app.services import rag

logger = logging.getLogger(__name__)

# Los trabajos terminados se conservan un rato para que el cliente alcance a leer el resultado.
FINISHED_TTL_SECONDS = 15 * 60

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ingest")
_jobs: dict[str, "_Job"] = {}
_lock = threading.Lock()


@dataclass
class _Job:
    doc_id: str
    session_id: str
    filename: str
    total: int
    seq: int  # orden de llegada, para calcular la posición en la cola
    status: str = "queued"
    processed: int = 0
    error: str | None = None
    document: DocumentInfo | None = None
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def active(self) -> bool:
        return self.status in ("queued", "processing")


_seq = 0


def submit(session_id: str, filename: str, data: bytes, prepared: rag.PreparedPdf) -> JobStatus:
    """Encola el procesamiento de un PDF ya validado (ver rag.prepare_pdf)."""
    global _seq
    with _lock:
        _prune()
        _seq += 1
        job = _Job(
            doc_id=uuid.uuid4().hex,
            session_id=session_id,
            filename=filename,
            total=len(prepared.chunks),
            seq=_seq,
        )
        _jobs[job.doc_id] = job
        status = _to_status(job)
    _executor.submit(_run, job, data, prepared)
    return status


def get(session_id: str, doc_id: str) -> JobStatus | None:
    with _lock:
        job = _jobs.get(doc_id)
        # Un trabajo de otra sesión es, para este cliente, inexistente.
        return _to_status(job) if job and job.session_id == session_id else None


def active_for_session(session_id: str) -> list[JobStatus]:
    with _lock:
        return [_to_status(j) for j in sorted(_jobs.values(), key=lambda j: j.seq) if j.session_id == session_id and j.active]


def count_active(session_id: str) -> int:
    with _lock:
        return sum(1 for j in _jobs.values() if j.session_id == session_id and j.active)


def _run(job: _Job, data: bytes, prepared: rag.PreparedPdf) -> None:
    with _lock:
        job.status = "processing"
        job.started_at = time.monotonic()

    def on_progress(done: int, total: int) -> None:
        with _lock:
            job.processed = done

    try:
        document = rag.index_pdf(job.session_id, job.doc_id, job.filename, data, prepared, on_progress=on_progress)
    except Exception:
        logger.exception("Falló el procesamiento de %s (%s)", job.filename, job.doc_id)
        with _lock:
            job.status = "error"
            job.error = "No se pudo procesar el documento. Intentá subirlo de nuevo."
            job.finished_at = time.monotonic()
        return

    with _lock:
        job.status = "ready"
        job.processed = job.total
        job.document = document
        job.finished_at = time.monotonic()


def _to_status(job: _Job) -> JobStatus:
    # Debe llamarse con _lock tomado.
    queue_position = (
        sum(1 for j in _jobs.values() if j.active and j.seq < job.seq) if job.status == "queued" else 0
    )
    end = job.finished_at or time.monotonic()
    elapsed = round(end - job.started_at, 1) if job.started_at is not None else 0
    return JobStatus(
        doc_id=job.doc_id,
        filename=job.filename,
        status=job.status,  # type: ignore[arg-type]
        processed=job.processed,
        total=job.total,
        queue_position=queue_position,
        elapsed_seconds=elapsed,
        error=job.error,
        document=job.document,
    )


def _prune() -> None:
    # Debe llamarse con _lock tomado.
    now = time.monotonic()
    expired = [d for d, j in _jobs.items() if j.finished_at is not None and now - j.finished_at > FINISHED_TTL_SECONDS]
    for doc_id in expired:
        del _jobs[doc_id]


def shutdown() -> None:
    _executor.shutdown(wait=False, cancel_futures=True)
