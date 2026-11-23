"""
Mide la calidad de la BÚSQUEDA (qué fragmentos se recuperan), sin llamar al LLM.

Uso (desde backend/, con el venv activado):
    python -m eval.retrieval --label base
    python -m eval.retrieval --label base --rewrite    # reescribe las preguntas de seguimiento con el LLM (usa Groq)

Indexa los PDFs de eval/pdfs con el código real de la app (en una carpeta temporal, sin tocar data/)
y pasa cada pregunta por rag.retrieve, la misma función que usa el chat. Así, cuando cambie la búsqueda
(híbrida, reranker...), este script mide el cambio sin modificarse.

Dos modos:
  solo   cada pregunta busca solo en su documento (como cuando el usuario filtra por documento)
  todos  busca en los 6 documentos a la vez: más difícil, porque los otros documentos meten ruido

Métricas (solo para las preguntas con respuesta en el documento):
  hit@k       % de preguntas en las que alguna de las k fuentes es de la página correcta
  frag@k      % en las que alguna fuente contiene la cita exacta (el fragmento justo, no solo la página)
  MRR         promedio de 1/posición de la primera fuente correcta (1 = siempre primera, 0.5 = segunda...)
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# La carpeta de datos tiene que definirse antes de cargar la configuración de la app.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="rag-eval-")

from app.config import get_settings  # noqa: E402
from app.models import HistoryMessage, Source  # noqa: E402
from app.services import rag  # noqa: E402
from eval.dataset import ANSWERABLE, EVAL_DIR, PDF_DIR, Item, load, normalize  # noqa: E402

RESULTS_DIR = EVAL_DIR / "results"
MODES = ("solo", "todos")
# Orden fijo para que las tablas de distintas corridas se puedan comparar a simple vista.
CATEGORY_ORDER = ["dato", "referencia", "numero", "otro_idioma", "seguimiento"]


def index_documents(session_id: str, filenames: list[str]) -> dict[str, str]:
    """Indexa los PDFs con el mismo camino que una subida real. Devuelve {nombre de archivo: doc_id}."""
    doc_ids = {}
    for filename in filenames:
        start = time.perf_counter()
        data = (PDF_DIR / filename).read_bytes()
        prepared = rag.prepare_pdf(data)
        doc_id = uuid.uuid4().hex
        rag.index_pdf(session_id, doc_id, filename, data, prepared)
        doc_ids[filename] = doc_id
        print(f"  {filename}: {len(prepared.chunks)} fragmentos en {time.perf_counter() - start:.1f} s")
    return doc_ids


def search_query(item: Item, rewrite: bool) -> str:
    if rewrite and item.history:
        return rag.rewrite_question(item.question, [HistoryMessage(**m) for m in item.history])
    return item.question


def score(item: Item, sources: list[Source]) -> dict:
    """Posición (1-based) de la primera fuente correcta por página y por fragmento; None si no está."""
    evidence = normalize(item.evidence)
    page_rank = next(
        (s.index for s in sources if s.filename == item.doc and s.page in item.pages), None
    )
    chunk_rank = next(
        (s.index for s in sources if s.filename == item.doc and evidence in normalize(s.text)), None
    )
    return {"page_rank": page_rank, "chunk_rank": chunk_rank}


def run(items: list[Item], rewrite: bool) -> list[dict]:
    session_id = uuid.uuid4().hex
    print("Indexando...")
    doc_ids = index_documents(session_id, sorted({i.doc for i in items}))

    rows = []
    for item in items:
        query = search_query(item, rewrite)
        for mode in MODES:
            filter_ids = [doc_ids[item.doc]] if mode == "solo" else None
            sources = rag.retrieve(session_id, query, filter_ids)
            row = {
                "id": item.id,
                "doc": item.doc,
                "category": item.category,
                "mode": mode,
                "question": item.question,
                "search_query": query,
                "top_score": sources[0].score if sources else None,
                "sources": [{"doc": s.filename, "page": s.page, "score": s.score} for s in sources],
            }
            if item.category in ANSWERABLE:
                row.update(score(item, sources))
            rows.append(row)
    return rows


def summarize(rows: list[dict], k: int) -> dict:
    """Métricas por modo y por categoría."""
    summary: dict = {}
    for mode in MODES:
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            if r["mode"] == mode and r["category"] in ANSWERABLE:
                groups[r["category"]].append(r)
                groups["TOTAL"].append(r)
        summary[mode] = {
            cat: {
                "n": len(rs),
                "hit": sum(r["page_rank"] is not None for r in rs) / len(rs),
                "frag": sum(r["chunk_rank"] is not None for r in rs) / len(rs),
                "mrr": sum(1 / r["page_rank"] for r in rs if r["page_rank"]) / len(rs),
            }
            for cat, rs in groups.items()
        }

    # Puntaje del mejor fragmento según si la pregunta tiene respuesta o no: muestra si un umbral
    # sobre ese puntaje podría separar "hay evidencia" de "no la hay" (ver el reranker).
    scores: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["mode"] == "solo" and r["top_score"] is not None:
            group = "con respuesta" if r["category"] in ANSWERABLE else r["category"]
            scores[group].append(r["top_score"])
    summary["top_score"] = {
        g: {"min": min(v), "mediana": statistics.median(v), "max": max(v)} for g, v in scores.items()
    }
    summary["k"] = k
    return summary


def print_report(summary: dict, rows: list[dict]) -> None:
    k = summary["k"]
    for mode in MODES:
        print(f"\nModo {mode!r}")
        print(f"  {'categoría':14} {'n':>3}  {f'hit@{k}':>7}  {f'frag@{k}':>7}  {'MRR':>5}")
        for cat in [*CATEGORY_ORDER, "TOTAL"]:
            m = summary[mode].get(cat)
            if m:
                print(f"  {cat:14} {m['n']:>3}  {m['hit']:>7.0%}  {m['frag']:>7.0%}  {m['mrr']:>5.2f}")

    print("\nPuntaje del mejor fragmento (modo 'solo')")
    for group, s in summary["top_score"].items():
        print(f"  {group:14} min {s['min']:.3f}  mediana {s['mediana']:.3f}  max {s['max']:.3f}")

    misses = [r for r in rows if r["mode"] == "solo" and r.get("page_rank", 0) is None]
    if misses:
        print(f"\nFallos en modo 'solo' (la página correcta no está entre las {k} fuentes):")
        for r in misses:
            got = ", ".join(str(s["page"]) for s in r["sources"])
            print(f"  {r['id']:9} {r['question'][:60]:60}  páginas traídas: {got}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default="sin-nombre", help="nombre de la corrida, p. ej. 'base' o 'hibrida'")
    parser.add_argument("--rewrite", action="store_true", help="reescribir las preguntas de seguimiento con el LLM")
    args = parser.parse_args()

    settings = get_settings()
    items = load()
    rows = run(items, args.rewrite)
    summary = summarize(rows, settings.top_k)
    print_report(summary, rows)

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"retrieval-{args.label}.json"
    config = {
        "label": args.label,
        "date": datetime.now().isoformat(timespec="seconds"),
        "rewrite": args.rewrite,
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
    }
    out.write_text(
        json.dumps({"config": config, "summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"\nResultados guardados en {out.relative_to(EVAL_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
