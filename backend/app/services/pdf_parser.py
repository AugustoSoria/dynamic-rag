import re
from dataclasses import dataclass

import pymupdf


class PdfError(Exception):
    """El PDF no se pudo procesar (corrupto, encriptado, sin texto, etc.)."""


@dataclass
class Page:
    number: int  # 1-indexed, como lo ve el usuario
    text: str


def _clean(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"-\n(?=[a-záéíóúñ])", "", text)  # une palabras cortadas con guion al final de línea
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pages(data: bytes, max_pages: int | None = None) -> list[Page]:
    """Extrae el texto de cada página. Lanza PdfError si el PDF no es utilizable."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PdfError("El archivo no es un PDF válido.") from exc

    with doc:
        if doc.needs_pass:
            raise PdfError("El PDF está protegido con contraseña.")
        if max_pages is not None and doc.page_count > max_pages:
            raise PdfError(f"El PDF tiene {doc.page_count} páginas; el máximo es {max_pages}.")

        pages = [Page(number=i + 1, text=_clean(page.get_text("text"))) for i, page in enumerate(doc)]

    pages = [p for p in pages if p.text]
    if not pages:
        raise PdfError("El PDF no tiene texto extraíble (posiblemente es un documento escaneado).")
    return pages
