"""
Mide la calidad de las RESPUESTAS: genera cada respuesta con el pipeline real del chat y la corrige
con un LLM más grande ("LLM como juez", la idea de RAGAS, pero en una sola llamada por respuesta).

Uso (desde backend/, con el venv activado):
    python -m eval.answers --label base
    python -m eval.answers --label base --limit 3       # prueba rápida con 3 preguntas
    python -m eval.answers --label base --rejudge       # vuelve a corregir sin regenerar las respuestas

Usa Groq: las respuestas salen de GROQ_MODEL (el modelo de la app) y la corrección de --judge.
Guarda el avance en results/answers-<label>.json después de cada pregunta: si se corta (límite de
uso, red...), al volver a correrlo retoma donde quedó.

Qué mide el juez en cada respuesta:
  correcta     compara con la respuesta de referencia del dataset: completa / parcial / incorrecta
  fidelidad    % de las afirmaciones de la respuesta que están respaldadas por las fuentes
               (1 = no inventó nada; es la "faithfulness" de RAGAS)
  dijo no sé   si la respuesta dice que el documento no tiene la información
Y sin LLM:
  citas        si cita al menos una fuente y todas las citas apuntan a fuentes que existen
"""

import argparse
import json
import re
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime

import groq

# Importar retrieval primero: define la carpeta temporal de datos antes de que se cargue la app.
from eval.retrieval import CATEGORY_ORDER, RESULTS_DIR, index_documents  # noqa: I001
from app.config import get_settings
from app.models import HistoryMessage
from app.services import llm, rag
from eval.dataset import ANSWERABLE, EVAL_DIR, UNANSWERABLE, Item, load

DEFAULT_JUDGE = "openai/gpt-oss-120b"
JUDGE_EFFORT = "medium"
JUDGE_TIMEOUT = 120  # segundos; una corrección normal tarda menos de 10
JUDGE_MAX_TOKENS = 4000  # razonamiento + JSON; una corrección normal usa ~1.000


class JudgeTruncatedError(Exception):
    """El juez agotó el máximo de tokens sin terminar el JSON (se reintenta)."""
MAX_ATTEMPTS = 8

JUDGE_PROMPT = """Sos un evaluador estricto de un asistente que responde preguntas sobre documentos.
Recibís la pregunta, las fuentes que el asistente tenía disponibles (fragmentos numerados del documento),
la respuesta del asistente y una respuesta de referencia escrita por una persona.

Evaluá tres cosas:

1. abstencion: true si la respuesta dice, en lo esencial, que el documento no contiene la información pedida
   (aunque agregue algún comentario). false si intenta responder.

2. afirmaciones: separá la respuesta en afirmaciones de hecho independientes y, para cada una, indicá si está
   respaldada por las fuentes (respaldada=true) o no (false).
   - Cada afirmación tiene que entenderse sola y conservar a qué o a quién se refiere: escribí "El artículo 18
     establece que nadie puede ser penado sin juicio previo", no solo "nadie puede ser penado sin juicio previo".
   - Verificá también esa atribución. Está respaldada si las fuentes la dicen o si se deduce de ellas de forma
     directa y segura (por ejemplo, por el orden del texto: lo que aparece justo antes de "Art. 14 bis" es el final
     del artículo 14). NO está respaldada si es una suposición: un ítem "18." de una lista numerada no alcanza para
     afirmar que es el "artículo 18", porque puede ser un inciso de otro artículo. En ese caso la afirmación no está
     respaldada aunque el texto citado sí aparezca.
   - Solo cuenta lo que dicen las fuentes, NO tu propio conocimiento: una afirmación verdadera que no está en las
     fuentes es respaldada=false.
   - No incluyas frases que solo dicen que no se encontró la información, ni fórmulas de cortesía. Si la respuesta
     es solo una abstención, la lista va vacía.

3. correccion, comparando con la respuesta de referencia:
   - "completa": contiene lo esencial de la referencia y no agrega nada falso o mal atribuido (puede decirlo con
     otras palabras o agregar detalles correctos).
   - "parcial": acierta una parte de lo esencial, pero le falta algo importante, o mezcla lo correcto con algún
     dato falso o mal atribuido.
   - "incorrecta": no contiene lo esencial o contradice la referencia.
   Si la referencia dice que el documento NO tiene la respuesta, lo correcto es abstenerse: "completa" si se abstuvo,
   "incorrecta" si respondió algo.

Explicá tu decisión de correccion en una oración, en "motivo"."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "abstencion": {"type": "boolean"},
        "afirmaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"texto": {"type": "string"}, "respaldada": {"type": "boolean"}},
                "required": ["texto", "respaldada"],
                "additionalProperties": False,
            },
        },
        "correccion": {"type": "string", "enum": ["completa", "parcial", "incorrecta"]},
        "motivo": {"type": "string"},
    },
    "required": ["abstencion", "afirmaciones", "correccion", "motivo"],
    "additionalProperties": False,
}

CORRECTNESS_SCORE = {"completa": 1.0, "parcial": 0.5, "incorrecta": 0.0}
# Mismos formatos que convierte el frontend (frontend/src/lib/citations.ts): [1], 【1】 y 【1†L3-L5】.
_CITATION_RE = re.compile(r"[\[【](\d+)(?:†[^\]】]*)?[\]】]")
NO_ANSWER_REFERENCE = "(El documento NO contiene esta información: lo correcto es decir que no se encontró.)"


def _retryable(exc: Exception) -> bool:
    # APIConnectionError incluye el timeout (APITimeoutError).
    if isinstance(exc, (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError, JudgeTruncatedError)):
        return True
    # Groq rechaza con 400 la salida del juez que no cumple el esquema JSON; suele salir bien al reintentar.
    return isinstance(exc, groq.BadRequestError) and "json_validate_failed" in str(exc)


def with_retries(fn, what: str):
    """Reintenta ante el límite de uso de Groq (8.000 tokens por minuto en el plan gratis) y errores pasajeros."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn()
        except (groq.APIError, JudgeTruncatedError) as exc:
            if not _retryable(exc) or attempt == MAX_ATTEMPTS:
                raise
            wait = 20.0
            response = getattr(exc, "response", None)
            if response is not None and response.headers.get("retry-after"):
                wait = float(response.headers["retry-after"]) + 1
            print(f"    {type(exc).__name__} en {what}: espero {wait:.0f} s (intento {attempt}/{MAX_ATTEMPTS})")
            time.sleep(wait)


# --- Generación ----------------------------------------------------------------

def generate(session_id: str, doc_id: str, item: Item) -> dict:
    """Pasa la pregunta por el mismo flujo que el endpoint de chat (reescritura → búsqueda → respuesta)."""
    history = [HistoryMessage(**m) for m in item.history]

    def run() -> dict:
        out = {"answer": "", "search_query": item.question, "sources": []}
        for event in rag.stream_answer(session_id, item.question, history, [doc_id]):
            if event.name == "sources":
                out["search_query"] = event.data["search_query"]
                out["sources"] = [
                    {"index": s["index"], "page": s["page"], "score": s["score"], "text": s["text"]}
                    for s in event.data["sources"]
                ]
            elif event.name == "token":
                out["answer"] += event.data["text"]
        return out

    start = time.perf_counter()
    out = with_retries(run, "la generación")
    out["seconds"] = round(time.perf_counter() - start, 1)
    return out


# --- Corrección ----------------------------------------------------------------

def judge(item: Item, row: dict, model: str) -> dict:
    sources = "\n\n".join(f"[{s['index']}] (página {s['page']})\n{s['text']}" for s in row["sources"])
    conversation = "".join(f"{m['role']}: {m['content']}\n" for m in item.history)
    user = (
        (f"Conversación previa:\n{conversation}\n" if conversation else "")
        + f"Pregunta: {item.question}\n\n"
        f"Fuentes:\n{sources or '(ninguna)'}\n\n"
        f"Respuesta del asistente:\n{row['answer']}\n\n"
        f"Respuesta de referencia:\n{item.answer or NO_ANSWER_REFERENCE}"
    )

    def run() -> dict:
        # Tope de tiempo y de tokens: a veces el modelo entra en un razonamiento interminable y, sin tope,
        # la corrida queda colgada esperando esa respuesta. Al cortarse, with_retries lo vuelve a intentar.
        response = llm._client().with_options(timeout=JUDGE_TIMEOUT).chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": "evaluacion", "strict": True, "schema": JUDGE_SCHEMA}},
            temperature=0,
            reasoning_effort=JUDGE_EFFORT,
            include_reasoning=False,
            max_completion_tokens=JUDGE_MAX_TOKENS,
        )
        if response.choices[0].finish_reason == "length":
            raise JudgeTruncatedError("la corrección se cortó por el máximo de tokens")
        result = json.loads(response.choices[0].message.content)
        result["tokens"] = response.usage.total_tokens
        return result

    return with_retries(run, "la corrección")


def citation_check(row: dict) -> dict:
    cited = {int(n) for n in _CITATION_RE.findall(row["answer"])}
    valid = {s["index"] for s in row["sources"]}
    return {"cites": bool(cited), "invalid_citations": sorted(cited - valid)}


# --- Métricas --------------------------------------------------------------------

def _faithfulness(j: dict) -> float | None:
    claims = j["afirmaciones"]
    return sum(c["respaldada"] for c in claims) / len(claims) if claims else None


def _mean(values: list[float | None]) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(rows: list[dict]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("judge"):
            groups[r["category"]].append(r)
            group = "con respuesta" if r["category"] in ANSWERABLE else "sin respuesta" if r["category"] in UNANSWERABLE else None
            if group:
                groups[group].append(r)

    summary = {}
    for name, rs in groups.items():
        answered = [r for r in rs if not r["judge"]["abstencion"]]
        summary[name] = {
            "n": len(rs),
            "correccion": _mean([CORRECTNESS_SCORE[r["judge"]["correccion"]] for r in rs]),
            "completas": sum(r["judge"]["correccion"] == "completa" for r in rs) / len(rs),
            "no_se": sum(r["judge"]["abstencion"] for r in rs) / len(rs),
            # Fidelidad solo de las que respondieron: una abstención no tiene afirmaciones que verificar.
            "fidelidad": _mean([_faithfulness(r["judge"]) for r in answered]),
            "con_invento": sum(_faithfulness(r["judge"]) not in (None, 1.0) for r in answered) / len(answered) if answered else None,
            "citas_ok": sum(r["citations"]["cites"] and not r["citations"]["invalid_citations"] for r in answered) / len(answered) if answered else None,
        }
    return summary


def _pct(v: float | None) -> str:
    return "  -" if v is None else f"{v:.0%}"


def print_report(summary: dict, rows: list[dict]) -> None:
    print(f"\n  {'categoría':14} {'n':>3}  {'corrección':>10}  {'completas':>9}  {'dijo no sé':>10}  {'fidelidad':>9}  {'con invento':>11}  {'citas ok':>8}")
    for name in [*CATEGORY_ORDER, "global", "sin_respuesta", "fuera_de_tema", "con respuesta", "sin respuesta"]:
        m = summary.get(name)
        if not m:
            continue
        if name == "con respuesta":
            print("  " + "-" * 92)
        print(
            f"  {name:14} {m['n']:>3}  {_pct(m['correccion']):>10}  {_pct(m['completas']):>9}  {_pct(m['no_se']):>10}"
            f"  {_pct(m['fidelidad']):>9}  {_pct(m['con_invento']):>11}  {_pct(m['citas_ok']):>8}"
        )

    print("\n  En 'con respuesta', 'dijo no sé' es un error (tenía la respuesta). En 'sin respuesta' es lo correcto.")
    bad = [r for r in rows if r.get("judge") and r["judge"]["correccion"] != "completa"]
    if bad:
        print("\nRespuestas no completas:")
        for r in bad:
            print(f"  {r['id']:9} {r['judge']['correccion']:10} {r['judge']['motivo'][:110]}")


# --- Main ------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--label", default="sin-nombre", help="nombre de la corrida, p. ej. 'base' o 'hibrida'")
    parser.add_argument("--judge", default=DEFAULT_JUDGE, help=f"modelo de Groq que corrige (por defecto {DEFAULT_JUDGE})")
    parser.add_argument("--limit", type=int, help="solo las primeras N preguntas (para probar)")
    parser.add_argument("--rejudge", action="store_true", help="volver a corregir todas, sin regenerar las respuestas")
    args = parser.parse_args()

    settings = get_settings()
    llm.ensure_configured()
    items = load()[: args.limit]

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"answers-{args.label}.json"
    saved = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    rows = {r["id"]: r for r in saved.get("rows", [])}
    if saved and saved["config"]["generator"] != settings.groq_model:
        print(f"{out_path.name} se generó con otro modelo ({saved['config']['generator']}): usá otro --label.")
        return 1
    config = {
        "label": args.label,
        "date": datetime.now().isoformat(timespec="seconds"),
        "generator": settings.groq_model,
        "judge": args.judge,
        "embedding_model": settings.embedding_model,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "top_k": settings.top_k,
        "retrieval_mode": settings.retrieval_mode,
    }

    def save() -> None:
        ordered = [rows[i.id] for i in items if i.id in rows]
        out_path.write_text(
            json.dumps({"config": config, "summary": summarize(ordered), "rows": ordered}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    pending = [i for i in items if "answer" not in rows.get(i.id, {})]
    if pending:
        session_id = uuid.uuid4().hex
        print("Indexando...")
        doc_ids = index_documents(session_id, sorted({i.doc for i in pending}))
        print(f"\nGenerando {len(pending)} respuestas con {settings.groq_model}...")
        for n, item in enumerate(pending, start=1):
            row = {"id": item.id, "doc": item.doc, "category": item.category, "question": item.question}
            row.update(generate(session_id, doc_ids[item.doc], item))
            rows[item.id] = row
            save()
            print(f"  [{n}/{len(pending)}] {item.id:9} {row['seconds']:>5} s  {row['answer'][:70]!r}")

    to_judge = [i for i in items if args.rejudge or not rows[i.id].get("judge")]
    if to_judge:
        print(f"\nCorrigiendo {len(to_judge)} respuestas con {args.judge}...")
        for n, item in enumerate(to_judge, start=1):
            row = rows[item.id]
            row["citations"] = citation_check(row)
            row["judge"] = judge(item, row, args.judge)
            save()
            print(f"  [{n}/{len(to_judge)}] {item.id:9} {row['judge']['correccion']:10} no sé={row['judge']['abstencion']!s:5}  fidelidad={_pct(_faithfulness(row['judge']))}")

    save()
    ordered = [rows[i.id] for i in items]
    print_report(summarize(ordered), ordered)
    print(f"\nResultados en {out_path.relative_to(EVAL_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
