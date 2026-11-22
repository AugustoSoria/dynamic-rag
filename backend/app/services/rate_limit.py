"""
Límite de uso por IP, en memoria (ventana deslizante).

Protege la cuota de Groq y la CPU del servidor de quien tenga la URL pública. Se limita por IP y no por
sesión porque el id de sesión lo genera el cliente: alcanza con cambiarlo para saltear un límite por sesión.

En memoria alcanza porque el backend corre en un único proceso (lo mismo exigen los trabajos en segundo
plano, ver services/jobs.py). Con varios procesos o réplicas haría falta un almacén compartido (Redis).
"""

import math
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: float, now: float | None = None) -> float | None:
        """
        Registra un uso de `key`. Devuelve None si está permitido, o los segundos que faltan para
        poder volver a intentar si se superó el límite (en ese caso el intento no se cuenta).
        """
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window_seconds - now
            hits.append(now)
            self._prune(now, window_seconds)
            return None

    def _prune(self, now: float, window_seconds: float) -> None:
        # Evita que el diccionario crezca sin fin con IPs que no volvieron.
        if len(self._hits) < 10_000:
            return
        for key in [k for k, h in self._hits.items() if not h or h[-1] <= now - window_seconds]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def format_wait(seconds: float) -> str:
    minutes = math.ceil(seconds / 60)
    return "1 minuto" if minutes <= 1 else f"{minutes} minutos"
