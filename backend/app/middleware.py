import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Margen para los encabezados del multipart (boundary, nombre del archivo, content-type).
_MULTIPART_OVERHEAD = 64 * 1024


class UploadSizeLimitMiddleware:
    """
    Corta las subidas que superan el tamaño máximo MIENTRAS llegan.

    Validarlo en el endpoint llega tarde: FastAPI parsea el multipart completo (y lo guarda en memoria
    o disco) antes de llamar a la función, así que un archivo de 2 GB se recibiría entero antes de
    rechazarlo. Este middleware:
      1. rechaza enseguida si el header Content-Length ya supera el límite, sin leer el body;
      2. si no hay Content-Length (transferencia por partes), cuenta los bytes a medida que llegan
         y corta apenas se pasa del límite.
    """

    def __init__(self, app: ASGIApp, path: str, max_mb: int) -> None:
        self.app = app
        self.path = path
        self.max_mb = max_mb
        self.max_bytes = max_mb * 1024 * 1024 + _MULTIPART_OVERHEAD

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != self.path:
            await self.app(scope, receive, send)
            return

        content_length = dict(scope["headers"]).get(b"content-length")
        if content_length is not None and content_length.isdigit() and int(content_length) > self.max_bytes:
            await self._reject(send)
            return

        received = 0
        exceeded = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    # Cortamos la lectura: FastAPI va a fallar al parsear el body y armar un 400,
                    # que reemplazamos abajo por un 413 con un mensaje claro.
                    raise _BodyTooLarge()
            return message

        response_started = False

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                if message["type"] == "http.response.start" and not response_started:
                    response_started = True
                    await self._reject(send)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _BodyTooLarge:
            if not response_started:
                await self._reject(send)

    async def _reject(self, send: Send) -> None:
        body = json.dumps({"detail": f"El archivo supera el máximo de {self.max_mb} MB."}, ensure_ascii=False).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})


class _BodyTooLarge(Exception):
    pass
