import uuid

import pytest

from app.config import get_settings
from app.services import keyword_index, rag, vector_store
from app.services.keyword_index import IndexedChunk, tokenize
from tests.conftest import make_pdf, upload_pdf


def test_tokenize_normalizes_accents_aliases_and_stopwords():
    assert tokenize("¿Qué dice el Artículo 14?") == ["art", "14"]
    assert tokenize("Art. 14 bis.- El trabajo") == ["art", "14", "bis", "trabajo"]
    assert tokenize("Murió en Ñuble") == ["murio", "nuble"]


def test_tokenize_keeps_numbers_with_separators():
    assert tokenize("Pan francés: 2.948,01 pesos, 193,0%") == ["pan", "frances", "2.948,01", "pesos", "193,0"]


CHUNKS = [
    IndexedChunk("a:0", "a", "Art. 14.- Todos los habitantes gozan del derecho de trabajar."),
    IndexedChunk("a:1", "a", "Art. 15.- En la Nación Argentina no hay esclavos."),
    IndexedChunk("b:0", "b", "Artículo 14. En caso de persecución, toda persona tiene derecho a buscar asilo."),
    IndexedChunk("b:1", "b", "Artículo 3. Todo individuo tiene derecho a la vida."),
]


def _search(query, doc_ids=None, chunks=CHUNKS, session=None):
    return keyword_index.search(session or uuid.uuid4().hex, query, 10, doc_ids, load=lambda: chunks)


def test_bm25_finds_exact_reference():
    results = _search("¿Qué dice el artículo 14?")
    assert set(results[:2]) == {"a:0", "b:0"}


def test_bm25_respects_document_filter():
    # b:1 ("Artículo 3") también coincide en "artículo", pero queda debajo.
    assert _search("artículo 14", doc_ids=["b"]) == ["b:0", "b:1"]


def test_bm25_without_matching_words_returns_nothing():
    assert _search("¿Qué es?") == []  # solo palabras vacías
    assert _search("fotosíntesis") == []


def test_index_is_cached_until_invalidated():
    session = uuid.uuid4().hex
    calls = []

    def load():
        calls.append(1)
        return CHUNKS

    keyword_index.search(session, "trabajar", 5, None, load=load)
    keyword_index.search(session, "asilo", 5, None, load=load)
    assert len(calls) == 1

    keyword_index.invalidate(session)
    keyword_index.search(session, "asilo", 5, None, load=load)
    assert len(calls) == 2


def test_index_built_with_stale_data_is_not_cached():
    session = uuid.uuid4().hex

    def load_and_change():
        # Simula que se sube un documento mientras se arma el índice.
        keyword_index.invalidate(session)
        return CHUNKS

    keyword_index.search(session, "asilo", 5, None, load=load_and_change)
    calls = []
    keyword_index.search(session, "asilo", 5, None, load=lambda: calls.append(1) or CHUNKS)
    assert calls == [1]  # se volvió a armar


def test_reciprocal_rank_fusion_rewards_agreement():
    fused = rag.reciprocal_rank_fusion([["x", "y", "z"], ["y", "w"]], k=60)
    assert fused[0] == "y"  # está en las dos listas
    assert set(fused) == {"x", "y", "z", "w"}


# --- De punta a punta, con Chroma y embeddings reales -----------------------------

# Páginas casi iguales que solo se distinguen por el código: los embeddings no separan bien números parecidos.
CODES = ["XQ-4417", "XQ-7441", "XQ-1447", "XQ-4174", "XQ-7414", "XQ-4471", "XQ-1744", "XQ-4714"]
PAGES = [f"El repuesto con código {code} fue descontinuado y se reemplaza por un modelo nuevo." for code in CODES]


@pytest.fixture
def hybrid(monkeypatch):
    monkeypatch.setattr(get_settings(), "retrieval_mode", "hybrid")


def test_hybrid_retrieval_finds_exact_code(client, session_headers, hybrid):
    upload_pdf(client, session_headers, data=make_pdf(PAGES), filename="repuestos.pdf")
    sources = rag.retrieve(session_headers["X-Session-ID"], "¿Qué pasó con el repuesto XQ-4471?")
    assert sources[0].page == 6


def test_keyword_search_recovers_what_semantic_search_missed(client, session_headers, hybrid, monkeypatch):
    """Si la búsqueda semántica no trae el fragmento, la de palabras clave lo suma, con su puntaje semántico."""
    session = session_headers["X-Session-ID"]
    upload_pdf(client, session_headers, data=make_pdf(PAGES), filename="repuestos.pdf")

    # La búsqueda semántica "falla": trae 3 candidatos equivocados. (Con solo 8 fragmentos no se puede simular
    # que traiga 7: estarían todos en las dos listas y la fusión, que premia aparecer en ambas, los pondría arriba.)
    real_search = vector_store.search
    monkeypatch.setattr(
        vector_store, "search", lambda *a, **kw: [c for c in real_search(*a, **kw) if c.page in (1, 2, 3)]
    )
    sources = rag.retrieve(session, "¿Qué pasó con el repuesto XQ-4471?")
    page6 = [s for s in sources if s.page == 6]
    assert page6, "el fragmento con el código tiene que llegar por BM25"
    assert 0.5 < page6[0].score <= 1  # similitud coseno calculada para el fragmento que no trajo la semántica


def test_hybrid_index_updates_after_upload_and_delete(client, session_headers, hybrid):
    session = session_headers["X-Session-ID"]
    upload_pdf(client, session_headers, pages_text=["Las lentejas se cocinan en 40 minutos."], filename="a.pdf")
    assert rag.retrieve(session, "lentejas")  # arma y cachea el índice

    r = upload_pdf(client, session_headers, pages_text=["El zirconio es un metal de transición."], filename="b.pdf")
    doc_b = r.json()["doc_id"]
    assert [s.filename for s in rag.retrieve(session, "zirconio")][0] == "b.pdf"

    client.delete(f"/api/documents/{doc_b}", headers=session_headers)
    assert all(s.filename == "a.pdf" for s in rag.retrieve(session, "zirconio"))
    assert vector_store.get_chunks([f"{doc_b}:0"], [0.0] * 384) == []
