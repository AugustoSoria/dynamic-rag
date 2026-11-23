# Evaluación

Conjunto de preguntas para medir la calidad del RAG y comparar el antes y el después de cada cambio (búsqueda híbrida, reranker, etc.).

- `pdfs/`: los documentos, con su fuente y licencia en [pdfs/README.md](pdfs/README.md).
- `dataset.jsonl`: las preguntas, una por línea.
- `dataset.py`: carga el dataset y lo valida.

## Formato

```json
{
  "id": "const-07",
  "doc": "constitucion_argentina.pdf",
  "category": "seguimiento",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "question": "¿Y para ser diputado?",
  "answer": "Veinticinco años, cuatro años de ciudadanía...",
  "pages": [21],
  "evidence": "Para ser diputado se requiere haber cumplido la edad de veinticinco años"
}
```

- `pages`: las páginas donde está la respuesta (alcanza con que la búsqueda traiga una).
- `evidence`: una cita textual del PDF. Permite comprobar que la página anotada es la correcta y, más adelante, medir si se recuperó el fragmento exacto y no solo la página.
- `answer`: respuesta de referencia, para evaluar las respuestas del LLM. Es `null` cuando el documento no tiene la respuesta.
- `history`: solo en las preguntas de seguimiento.

## Categorías

| Categoría | Qué mide | Ejemplo |
|---|---|---|
| `dato` | Un dato puntual, preguntado con otras palabras que las del documento | "¿Quién es el comandante en jefe de las fuerzas armadas?" |
| `referencia` | Referencias exactas, el punto débil de la búsqueda semántica | "¿Qué dice el artículo 14?" |
| `numero` | Cifras, incluidas las de tablas | "¿Cuánto costaba el kilo de pan francés?" |
| `otro_idioma` | Pregunta en español sobre un documento en inglés | "¿Qué porcentaje se retiene con el backup withholding?" |
| `seguimiento` | Preguntas que solo se entienden con la conversación previa | "¿Y para ser diputado?" |
| `global` | Preguntas sobre el documento entero (no tienen una página correcta) | "¿De qué trata este documento?" |
| `sin_respuesta` | Del tema del documento, pero sin respuesta en él: debe decir que no lo encontró | "¿Cuál fue la inflación de noviembre?" (el informe es de octubre) |
| `fuera_de_tema` | Nada que ver con el documento | "¿Quién ganó el mundial 2022?" |

"¿Qué dice el artículo 14?" aparece dos veces a propósito: en la Constitución (derechos de los habitantes) y en la Declaración de Derechos Humanos (asilo). Con los dos documentos cargados, la búsqueda tiene que traer el artículo del documento correcto.

## Medir la búsqueda

Desde `backend/` con el venv activado:

```
python -m eval.retrieval --label base
```

Indexa los PDFs con el código real de la app (en una carpeta temporal, sin tocar `data/`) y pasa cada pregunta por `rag.retrieve`, la misma función que usa el chat. No llama al LLM, tarda menos de un minuto y da siempre el mismo resultado. Con `--rewrite`, las preguntas de seguimiento se reescriben con el LLM antes de buscar, como en el chat (usa Groq).

Mide en dos modos: `solo` (cada pregunta busca en su documento) y `todos` (busca en los 6 a la vez, con más ruido). Para las preguntas con respuesta:

- **hit@5**: % de preguntas en las que alguna de las 5 fuentes es de la página correcta.
- **frag@5**: % en las que alguna fuente contiene la cita exacta. Es más estricta: en "¿Qué dice el artículo 14?" la búsqueda puede traer la página 11 por el artículo 14 bis, que está en la misma página, sin traer el 14.
- **MRR**: qué tan arriba aparece la primera fuente correcta (1 = siempre primera, 0,5 = siempre segunda).

Cada corrida queda en `results/retrieval-<label>.json`. `retrieval-base.json` es la línea base, antes de cualquier mejora.

## Validar

Después de editar el dataset, desde `backend/` con el venv activado:

```
python -m eval.dataset
```

Usa el mismo parser y chunker que la app, y falla si alguna `evidence` no está en las páginas anotadas.
