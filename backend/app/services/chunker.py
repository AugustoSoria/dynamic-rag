from dataclasses import dataclass

from app.services.pdf_parser import Page

# Separadores preferidos para cortar, de mejor a peor.
_SEPARATORS = ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ")


@dataclass
class Chunk:
    text: str
    page: int
    chunk_index: int


def _find_cut(text: str, start: int, end: int) -> int:
    """Busca el mejor punto de corte en text[start:end], prefiriendo la segunda mitad de la ventana."""
    min_cut = start + (end - start) // 2
    for sep in _SEPARATORS:
        pos = text.rfind(sep, min_cut, end)
        if pos != -1:
            return pos + len(sep)
    return end


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap debe ser menor que chunk_size")
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            end = _find_cut(text, start, end)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        # Retrocede `overlap` caracteres, alineando al inicio de una palabra.
        next_start = max(end - overlap, start + 1)
        space = text.find(" ", next_start, end)
        start = space + 1 if space != -1 else next_start
    return chunks


def chunk_pages(pages: list[Page], chunk_size: int, overlap: int) -> list[Chunk]:
    """Divide cada página por separado, así cada chunk conserva su número de página para las citas."""
    chunks: list[Chunk] = []
    for page in pages:
        for piece in split_text(page.text, chunk_size, overlap):
            chunks.append(Chunk(text=piece, page=page.number, chunk_index=len(chunks)))
    return chunks
