"""
Carga y valida el dataset de evaluación (eval/dataset.jsonl).

Uso (desde backend/, con el venv activado):
    python -m eval.dataset

La validación comprueba que cada `evidence` esté en las páginas anotadas, usando el mismo parser y
chunker que la app. Así una página mal anotada no pasa desapercibida y arruina las métricas.
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
PDF_DIR = EVAL_DIR / "pdfs"
DATASET_PATH = EVAL_DIR / "dataset.jsonl"

# Con respuesta en el documento: tienen páginas y evidencia, y sirven para medir la búsqueda.
ANSWERABLE = {"dato", "referencia", "numero", "otro_idioma", "seguimiento"}
# Sin respuesta en el documento: lo correcto es decir que no se encontró.
UNANSWERABLE = {"sin_respuesta", "fuera_de_tema"}
# Sobre el documento entero: no hay una página "correcta".
GLOBAL = {"global"}
CATEGORIES = ANSWERABLE | UNANSWERABLE | GLOBAL


@dataclass
class Item:
    id: str
    doc: str
    category: str
    question: str
    answer: str | None
    pages: list[int]
    evidence: str | None
    history: list[dict] = field(default_factory=list)

    @property
    def answerable(self) -> bool:
        return self.category in ANSWERABLE


def normalize(text: str) -> str:
    """Compara sin importar saltos de línea ni espacios repetidos (el PDF corta las líneas donde quiere)."""
    return re.sub(r"\s+", " ", text).strip()


def load(path: Path = DATASET_PATH) -> list[Item]:
    items = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            try:
                items.append(Item(**json.loads(line)))
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"{path.name}, línea {n}: {exc}") from exc
    return items


def _schema_errors(item: Item) -> list[str]:
    errors = []
    if item.category not in CATEGORIES:
        errors.append(f"categoría desconocida: {item.category}")
    if not (PDF_DIR / item.doc).is_file():
        errors.append(f"no existe el PDF {item.doc}")
    if item.answerable:
        if not item.pages or not item.evidence or not item.answer:
            errors.append("una pregunta con respuesta necesita pages, evidence y answer")
    elif item.pages or item.evidence:
        errors.append(f"una pregunta '{item.category}' no lleva pages ni evidence")
    if item.category in UNANSWERABLE and item.answer is not None:
        errors.append("una pregunta sin respuesta lleva answer null")
    if item.category in GLOBAL and not item.answer:
        errors.append("una pregunta global necesita una answer de referencia")
    if (item.category == "seguimiento") != bool(item.history):
        errors.append("history va solo (y siempre) en las preguntas de seguimiento")
    return errors


def validate(items: list[Item]) -> list[str]:
    # Import tardío: cargar la app solo hace falta para validar, no para leer el dataset.
    sys.path.insert(0, str(EVAL_DIR.parent))
    from app.config import get_settings
    from app.services import chunker, pdf_parser

    settings = get_settings()
    errors, warnings = [], []

    dup = [i for i, c in Counter(item.id for item in items).items() if c > 1]
    errors += [f"id repetido: {i}" for i in dup]

    docs: dict[str, tuple[dict[int, str], list[str]]] = {}
    for item in items:
        errors += [f"{item.id}: {e}" for e in _schema_errors(item)]
        if not item.answerable or not (PDF_DIR / item.doc).is_file():
            continue

        if item.doc not in docs:
            parsed = pdf_parser.extract_pages((PDF_DIR / item.doc).read_bytes())
            chunks = chunker.chunk_pages(parsed.pages, settings.chunk_size, settings.chunk_overlap)
            docs[item.doc] = ({p.number: normalize(p.text) for p in parsed.pages}, [normalize(c.text) for c in chunks])
        pages, chunks = docs[item.doc]

        evidence = normalize(item.evidence)
        found_in = [n for n, text in pages.items() if evidence in text]
        if not found_in:
            errors.append(f"{item.id}: la evidencia no aparece en ninguna página del PDF")
        elif not set(found_in) & set(item.pages):
            errors.append(f"{item.id}: la evidencia está en las páginas {found_in}, no en las anotadas {item.pages}")
        if found_in and not any(evidence in c for c in chunks):
            warnings.append(f"{item.id}: la evidencia queda partida entre dos fragmentos (solo cuenta el acierto por página)")

    for w in warnings:
        print(f"  aviso  {w}")
    return errors


def main() -> int:
    items = load()
    errors = validate(items)
    for e in errors:
        print(f"  ERROR  {e}")

    print(f"\n{len(items)} preguntas en {len({i.doc for i in items})} documentos")
    for category, count in sorted(Counter(i.category for i in items).items()):
        print(f"  {category:15} {count}")
    print("\nOK" if not errors else f"\n{len(errors)} errores")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
