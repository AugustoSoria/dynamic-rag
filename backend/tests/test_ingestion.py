import pytest

from app.services.chunker import chunk_pages, split_text
from app.services.pdf_parser import Page, PdfError, extract_pages
from tests.conftest import make_pdf


# --- chunker ---------------------------------------------------------------

def test_short_text_is_single_chunk():
    assert split_text("hola mundo", chunk_size=100, overlap=10) == ["hola mundo"]


def test_chunks_respect_size_and_cover_text():
    text = " ".join(f"Oración número {i}." for i in range(200))
    chunks = split_text(text, chunk_size=200, overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert chunks[0].startswith("Oración número 0.")
    assert chunks[-1].endswith("Oración número 199.")


def test_chunks_overlap():
    text = " ".join(f"palabra{i}" for i in range(300))
    chunks = split_text(text, chunk_size=150, overlap=50)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.split()[0] in prev  # el inicio de cada chunk aparece al final del anterior


def test_invalid_overlap():
    with pytest.raises(ValueError):
        split_text("x" * 100, chunk_size=10, overlap=10)


def test_chunk_pages_keeps_page_numbers():
    pages = [Page(1, "a " * 300), Page(2, "b " * 50)]
    chunks = chunk_pages(pages, chunk_size=200, overlap=20)
    assert {c.page for c in chunks} == {1, 2}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


# --- pdf parser ------------------------------------------------------------

def test_extract_pages_skips_empty_pages():
    pages = extract_pages(make_pdf(["Primera página", "", "Tercera página"]))
    assert [p.number for p in pages] == [1, 3]
    assert pages[0].text == "Primera página"


def test_pdf_without_text_raises():
    with pytest.raises(PdfError, match="texto extraíble"):
        extract_pages(make_pdf(["", ""]))


def test_invalid_pdf_raises():
    with pytest.raises(PdfError, match="no es un PDF"):
        extract_pages(b"esto no es un pdf")


def test_max_pages():
    with pytest.raises(PdfError, match="máximo"):
        extract_pages(make_pdf(["a", "b", "c"]), max_pages=2)
