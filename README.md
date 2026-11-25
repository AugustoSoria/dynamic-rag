# Dynamic RAG

Subí uno o varios PDFs y hacele preguntas. Cada respuesta cita las páginas de donde sale, y al hacer clic en una cita el documento se abre en esa página con el fragmento resaltado.

**Demo:** https://dynamic-rag-five.vercel.app

![Respuesta con citas y el fragmento citado resaltado en el visor](docs/screenshot.png)

## Funcionalidades

- **Respuestas con citas verificables.** Cada afirmación lleva un número `[n]`. Al hacer clic, el visor abre el PDF en esa página y resalta el fragmento exacto.
- **Streaming.** La respuesta aparece palabra por palabra.
- **Búsqueda híbrida.** Combina la búsqueda semántica con la de palabras clave (BM25), así encuentra tanto preguntas dichas con otras palabras como referencias exactas ("¿qué dice el artículo 14?"), cifras y nombres.
- **Conversación con memoria.** Las preguntas de seguimiento ("¿y dónde nació?") se reescriben con el contexto de la charla antes de buscar.
- **Calidad medida.** Un conjunto de 69 preguntas sobre 6 PDFs reales mide la búsqueda y las respuestas antes y después de cada cambio (ver [Evaluación](#evaluación)).
- **Varios documentos.** Se puede buscar en todos o elegir en cuáles.
- **Procesamiento en segundo plano con progreso real.** Muestra los fragmentos procesados, la posición en la cola y el tiempo restante. Si se recarga la página, el progreso se retoma.
- **Sesiones anónimas y temporales.** No hay registro. Los documentos de cada visitante están aislados de los demás y se borran solos tras 2 horas sin actividad.
- **Validaciones con mensajes claros.** La app rechaza PDFs protegidos con contraseña, escaneados sin texto, de más de 300 páginas o de más de 20 MB.

## Cómo funciona

```mermaid
flowchart LR
    subgraph Ingesta["Al subir un PDF (en segundo plano)"]
        A[PDF] --> B[Extraer texto<br/>por página]
        B --> C[Dividir en fragmentos<br/>~800 caracteres]
        C --> D[Embeddings<br/>multilingual-e5-small]
        D --> E[(ChromaDB)]
    end
    subgraph Consulta["Al preguntar"]
        F[Pregunta +<br/>historial] --> G[Reescribir la pregunta<br/>con el contexto]
        G --> H1[Búsqueda semántica<br/>20 candidatos]
        G --> H2[Búsqueda BM25<br/>20 candidatos]
        E --> H1
        E --> H2
        H1 --> H[Fusión RRF:<br/>los 5 mejores]
        H2 --> H
        H --> I[gpt-oss-20b en Groq<br/>con los fragmentos numerados]
        I --> J[Respuesta en streaming<br/>con citas]
    end
```

1. **Ingesta.** PyMuPDF extrae el texto de cada página, que se divide en fragmentos de unos 800 caracteres con 150 de superposición. Cada fragmento guarda su página de origen. Los embeddings se generan localmente con `intfloat/multilingual-e5-small`, un modelo multilingüe y liviano que anda bien en español, y se guardan en ChromaDB con la sesión y el documento como metadatos.
2. **Consulta.** Si hay historial, el LLM primero reescribe la pregunta para que se entienda sola. Por ejemplo, "¿y dónde nació?" pasa a ser "¿Dónde nació Víctor Jara?". Con esa versión se hacen dos búsquedas, filtrando por la sesión y los documentos elegidos: una semántica en ChromaDB y otra por palabras clave con BM25. Cada una aporta 20 candidatos y se combinan con *reciprocal rank fusion*, que premia a los fragmentos bien ubicados en las dos listas. Quedan los 5 mejores.
3. **Respuesta.** El LLM recibe los fragmentos numerados y la instrucción de responder solo con esa información, citando cada dato. El backend envía primero las fuentes y después los tokens por Server-Sent Events.

## Decisiones técnicas

| Decisión | Por qué |
|---|---|
| **Groq con `openai/gpt-oss-20b`** | Responde muy rápido (cientos de tokens por segundo) y tiene un plan gratis que alcanza para una demo. |
| **Embeddings locales** en lugar de una API | Sin costo por documento ni otra API key. Además, el documento completo no sale del servidor: al LLM solo llegan los 5 fragmentos de cada pregunta. |
| **ChromaDB** | Persistente en disco, con filtros por metadatos (sesión y documento) y sin un servicio aparte. |
| **Búsqueda híbrida con BM25 propio** | Los embeddings encuentran ideas parecidas, pero confunden "artículo 14" con "artículo 14 bis" o no encuentran una cifra puntual; BM25 los resuelve por coincidencia de palabras. Está implementado en unas 40 líneas, sin dependencias nuevas: el índice de cada sesión se arma con los textos que ya guarda ChromaDB, se cachea en memoria y se invalida al subir o borrar documentos. La fusión usa solo las posiciones (RRF) porque los puntajes de las dos búsquedas no son comparables. Con `RETRIEVAL_MODE=vector` se vuelve a la búsqueda solo semántica. |
| **Reescritura de la pregunta** | Sin ella, "¿y dónde nació?" busca literalmente esas palabras y no encuentra nada útil. |
| **Procesamiento en segundo plano** | Un PDF largo tarda minutos en la CPU del servidor, y los proxies cortan las peticiones largas. La subida responde enseguida (202) y el cliente consulta el avance. Los fragmentos se guardan juntos al final, así una búsqueda nunca ve un documento a medio procesar. |
| **Historial enviado por el cliente** | El backend no guarda estado de la conversación: cada pregunta trae su historial, recortado a los últimos 6 mensajes. |
| **Validación del tamaño mientras llega el archivo** | Un middleware ASGI corta la subida apenas pasa los 20 MB, en vez de recibir el archivo entero y recién después rechazarlo. |

## Stack

- **Backend:** Python, FastAPI, PyMuPDF, sentence-transformers, ChromaDB, Groq SDK.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS 4, TanStack Query, react-pdf (pdf.js), react-markdown.
- **Tests:** pytest, Vitest y Playwright (E2E con video, en escritorio y celular).
- **Infraestructura:** Docker Compose, Caddy, AWS (EC2, CloudFront, SSM Parameter Store y CloudFormation) y Vercel.

## Correr en local

Requisitos: Python 3.10 o superior, Node 20.19 o superior y una API key de [Groq](https://console.groq.com/keys) (es gratis).

Los comandos son para **cmd** de Windows. En Linux o macOS, activá el entorno con `source .venv/bin/activate` y usá `cp` en lugar de `copy`.

**Backend** (http://localhost:8000, documentación de la API en `/docs`):

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
```

Completá `GROQ_API_KEY` en `backend\.env` y levantá el servidor:

```
uvicorn app.main:app --reload
```

La primera vez descarga el modelo de embeddings, que pesa unos 470 MB.

**Frontend** (http://localhost:5173), en otra consola:

```
cd frontend
npm install
npm run dev
```

Vite reenvía `/api` al backend local, así que no hace falta configurar nada más.

**Con Docker**, como en producción: backend y Caddy con HTTPS en https://localhost.

```
copy .env.example .env
docker compose up -d --build
```

## Tests

```
cd backend
.venv\Scripts\activate
pytest
```

```
cd frontend
npm test
npm run e2e:ui
npm run e2e
```

- `npm test` corre las pruebas unitarias con Vitest.
- `npm run e2e:ui` corre los tests E2E de interfaz, que no llaman al LLM.
- `npm run e2e` corre todos los E2E, incluidos los de calidad de respuestas, que sí usan la cuota de Groq.

- **Backend:** ingesta y casos borde de PDFs, búsqueda híbrida, chat con un LLM simulado, API de documentos, trabajos en segundo plano, limpieza de sesiones y límite de uso.
- **E2E:** levantan el backend y el frontend solos. Graban un video de cada test, que se ve con `npm run e2e:report`. Los PDFs de prueba se generan con `backend/scripts/make_test_pdfs.py`.

> En Windows, Vitest y `docker compose build` fallan si la ruta empieza con `c:\` en minúscula: abrí la consola en `C:\...`.

## Evaluación

[`backend/eval/`](backend/eval/README.md) tiene 69 preguntas sobre 6 PDFs reales (la Constitución Argentina, la Declaración Universal de Derechos Humanos, un informe del INDEC, un formulario del IRS y artículos de Wikipedia), cada una con la página correcta, una cita textual y una respuesta de referencia. Incluye referencias exactas, cifras de tablas, preguntas en otro idioma, de seguimiento y sin respuesta en el documento.

- **Búsqueda** (`python -m eval.retrieval`): si el fragmento con la respuesta llega entre las 5 fuentes. Sin LLM, en menos de un minuto.
- **Respuestas** (`python -m eval.answers`): genera cada respuesta con el flujo real del chat y la corrige `gpt-oss-120b` como juez: si coincide con la referencia, si cada afirmación está respaldada por las fuentes (como la *faithfulness* de RAGAS) y si dice "no sé" cuando corresponde.

Resultado de la búsqueda híbrida, sobre las preguntas con respuesta en el documento:

| | Fragmento correcto entre las 5 fuentes | Respuestas completas | Dice "no sé" teniendo la respuesta |
|---|---|---|---|
| Solo semántica | 86% | 79% | 9% |
| Híbrida | **93%** | **88%** | **2%** |

En las 9 preguntas sin respuesta en el documento, dice que no la encontró en todos los casos. El detalle, pregunta por pregunta, está en [`backend/eval/README.md`](backend/eval/README.md).

## Deploy

```
navegador ──HTTPS──► Vercel (frontend)
          ──HTTPS──► CloudFront ──HTTP──► EC2 t3.small: Caddy ──► FastAPI (Docker Compose)
```

Toda la infraestructura de AWS está en [`infra/cloudformation.yml`](infra/cloudformation.yml):

- **Una EC2 t3.small** (2 GB de RAM) con Ubuntu. En el primer arranque instala Docker, clona el repo y levanta la app como servicio de systemd.
- **CloudFront delante de la EC2.** Da HTTPS sin necesidad de un dominio propio. El puerto 80 de la instancia solo acepta tráfico de CloudFront, y el backend toma la IP real del usuario del encabezado `CloudFront-Viewer-Address`.
- **La API key de Groq** se guarda en SSM Parameter Store como SecureString. La instancia la lee al arrancar con un rol IAM de solo lectura, así que nunca queda escrita en la plantilla.
- **Sin SSH:** se entra con Session Manager.
- **La imagen de Docker** usa PyTorch solo para CPU, trae el modelo de embeddings incluido y arranca sin conexión a Hugging Face.

### Pasos

1. Crear el proyecto en Vercel con `frontend` como directorio raíz y anotar su URL.
2. En Systems Manager → Parameter Store, crear `/dynamic-rag/groq-api-key` de tipo **SecureString** con la API key.
3. En CloudFormation, crear un stack con `infra/cloudformation.yml`. Completar `CorsOrigin` con la URL de Vercel y `AlertEmail` con un email, y tildar el aviso de IAM. La app tarda de 5 a 10 minutos en estar lista; el output `HealthCheck` lo confirma.
4. En Vercel, definir `VITE_API_URL` con el output `BackendUrl` y volver a hacer el deploy.

Para actualizar el servidor después de un push, desde Session Manager:

```
cd /opt/dynamic-rag && sudo git pull && sudo systemctl restart dynamic-rag
```

## Limitaciones conocidas

- **Preguntas que no comparten palabras con el texto.** Si la pregunta usa sinónimos ("¿con quién se casó?" cuando el texto dice "esposa") o está en otro idioma que el documento, BM25 no ayuda y la búsqueda semántica a veces tampoco alcanza. Un reranker (un modelo que lee la pregunta y cada fragmento juntos) lo mejoraría, y daría además un puntaje confiable para decir "no sé" sin depender solo del prompt.
- **Fragmentos sin contexto.** Un fragmento que empieza en "18. Proveer lo conducente…" no dice que es el inciso 18 del artículo 75, y el modelo puede tomarlo por el artículo 18. Agregarle a cada fragmento el título de su sección lo resolvería.
- **Ideas cortadas entre fragmentos.** Si un párrafo largo queda dividido, la respuesta puede salir incompleta. Recuperar también los fragmentos vecinos ayudaría.
- **Preguntas globales.** "¿De qué trata el documento?" se responde con los 5 fragmentos más parecidos, no con el documento entero. Un resumen generado al subir el PDF lo mejoraría.
- **Texto ilegible.** Algunos PDFs con fuentes sin mapeo a Unicode extraen caracteres basura y se aceptan igual. Habría que detectarlo y avisar.
- **Un solo proceso.** La cola de trabajos y el límite de uso viven en memoria. Para escalar a varias réplicas harían falta un almacén compartido, como Redis, y una base vectorial como servicio.

## Estructura

```
backend/
  app/
    api/          endpoints (documentos, chat) y dependencias (sesión, límite de uso)
    services/     pdf_parser, chunker, embeddings, vector_store, keyword_index, rag, llm, jobs, sessions
  tests/
  eval/           dataset de evaluación, PDFs y scripts que miden la búsqueda y las respuestas
  scripts/        generador de PDFs de prueba
frontend/
  src/
    api/          cliente HTTP y parser de SSE
    hooks/        sesión, documentos (subida y progreso), chat
    components/   layout, chat, visor de PDF
    lib/          citas y resaltado de fragmentos
  e2e/            tests de Playwright
infra/            plantilla de CloudFormation
```
