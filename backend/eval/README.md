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

## Medir las respuestas

```
python -m eval.answers --label base
```

Genera cada respuesta con el flujo real del chat (reescritura de la pregunta → búsqueda → respuesta, con `GROQ_MODEL`) y la corrige con un modelo más grande, `openai/gpt-oss-120b` ("LLM como juez"). Es la misma idea que RAGAS, pero en una sola llamada por respuesta en lugar de varias: RAGAS necesitaría más de 300.000 tokens por corrida, más de lo que permite el plan gratis de Groq en un día. Una corrida usa unos 250.000 tokens repartidos entre los dos modelos y tarda unos 40 minutos, sobre todo por el límite de 8.000 tokens por minuto.

El juez devuelve, para cada respuesta:

- **corrección**: comparada con la respuesta de referencia, `completa` (1), `parcial` (0,5) o `incorrecta` (0).
- **fidelidad**: la respuesta separada en afirmaciones, cada una marcada como respaldada o no por las fuentes. Es la *faithfulness* de RAGAS: mide si el modelo inventó algo, aunque sea verdad. "Con invento" es el % de respuestas con al menos una afirmación sin respaldo.
- **dijo no sé**: si respondió que el documento no tiene la información. En las preguntas con respuesta es un error; en `sin_respuesta` y `fuera_de_tema` es lo correcto.

Y sin LLM, **citas ok**: que la respuesta cite al menos una fuente y que todas las citas apunten a fuentes que existen.

El avance se guarda después de cada pregunta en `results/answers-<label>.json`: si se corta, al volver a correrlo retoma donde quedó. Con `--rejudge` se vuelve a corregir sin regenerar las respuestas (útil al ajustar el juez) y con `--limit 3` se prueba con pocas preguntas.

**Limitaciones del juez.** Como todo LLM juez, se equivoca a veces y su nota varía un poco entre corridas, así que diferencias de pocos puntos entre dos corridas no son significativas. Un caso conocido: en "¿Qué dice el artículo 18?" el bot le atribuye al artículo 18 el inciso 18 del artículo 75 (el fragmento empieza con "18. Proveer lo conducente…" sin decir de qué artículo es), y el juez no lo detecta. Conviene revisar a mano las respuestas marcadas como no completas.

## Línea base (antes de las mejoras)

Búsqueda (`results/retrieval-base.json`): el fragmento con la respuesta está entre las 5 fuentes en el **86%** de las preguntas buscando en un documento y en el **82%** buscando en los 6. Lo más débil: referencias exactas, preguntas en otro idioma y de seguimiento.

Respuestas (`results/answers-base.json`), según el juez:

| | n | completas | dijo no sé | con invento |
|---|---|---|---|---|
| Con respuesta en el documento | 57 | 79% | 9% (error) | 2% |
| Sin respuesta en el documento | 9 | 100% | 100% (correcto) | - |
| Globales ("¿de qué trata?") | 3 | 0% | 0% | 67% |

Revisión a mano de las 15 respuestas no completas:

- **6 fallan porque la búsqueda no trajo el fragmento correcto** (const-01, jara-03, indec-02, indec-03, w9-02, w9-05). Son las 6 marcadas como incorrectas: en 5 el bot dice que no encontró la información aunque está en el documento, y en indec-02 responde un número equivocado (3,2% en vez de 193,0%), que sacó de un gráfico cuyo texto extraído es una lista de números sin rótulos. **Es el problema principal, y es justo el que atacan la búsqueda híbrida y el reranker.**
- **3 son las preguntas globales**: con 5 fragmentos no se puede resumir un documento entero (limitación conocida, ver el README principal).
- **2 son errores del LLM con las fuentes correctas**: jara-01 agrega que "el consenso es San Ignacio", algo que el documento no dice, y ddhh-04 omite el inciso 2 del artículo 14, que estaba en las fuentes.
- **4 están bien respondidas, pero el juez es estricto**: le faltan detalles de la referencia que la pregunta no pedía (por ejemplo, "¿Cuánto duran los senadores?" → "seis años", sin aclarar que son reelegibles). Con ellas, las respuestas aceptables suben del 79% al ~86%.

No hubo inventos con la evidencia a la vista, y en las 9 preguntas sin respuesta dijo "no sé" siempre: el prompt funciona. El juez tuvo un error claro: en indec-02 marcó como respaldado el 3,2% (el número está en la fuente, pero no es la variación interanual). La fidelidad puede sobrestimarse cuando la fuente es una tabla desordenada.

## Validar

Después de editar el dataset, desde `backend/` con el venv activado:

```
python -m eval.dataset
```

Usa el mismo parser y chunker que la app, y falla si alguna `evidence` no está en las páginas anotadas.
