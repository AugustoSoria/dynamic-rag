import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException


def get_session_id(
    x_session_id: Annotated[str, Header(description="UUID de sesión generado por el cliente")],
) -> str:
    """Valida el header X-Session-ID. Se usa como nombre de carpeta, así que debe ser un UUID estricto."""
    try:
        return str(uuid.UUID(x_session_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Session-ID debe ser un UUID válido.")


def normalize_doc_id(doc_id: str) -> str:
    """Los doc_id son UUID en hex. Cualquier otro valor se trata como inexistente."""
    try:
        return uuid.UUID(hex=doc_id).hex
    except ValueError:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")


SessionId = Annotated[str, Depends(get_session_id)]
DocId = Annotated[str, Depends(normalize_doc_id)]
