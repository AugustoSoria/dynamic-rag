# PDFs de evaluación

Documentos reales para medir la calidad del RAG (búsqueda y respuestas). Se eligieron para cubrir casos distintos, y todos permiten redistribuirlos.

| Archivo | Páginas | Idioma | Qué pone a prueba | Fuente y licencia |
|---|---|---|---|---|
| `constitucion_argentina.pdf` | 60 | es | Documento largo con artículos numerados: referencias exactas ("¿qué dice el artículo 14?") | Constitución de la Nación Argentina, edición de la Biblioteca del Congreso de la Nación (2023). El texto de la ley es de dominio público. |
| `declaracion_derechos_humanos.pdf` | 9 | es | Artículos numerados y redacción parecida entre artículos (fragmentos fáciles de confundir) | Declaración Universal de Derechos Humanos, Naciones Unidas. Reproducción libre. |
| `victor_jara_wikipedia.pdf` | 12 | es | Biografía: nombres, fechas, lugares y preguntas de seguimiento | Artículo "Víctor Jara" de Wikipedia en español ([revisión 176248960](https://es.wikipedia.org/w/index.php?title=V%C3%ADctor_Jara&oldid=176248960)). [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.es). |
| `indec_ipc_octubre_2024.pdf` | 19 | es | Tablas y gráficos con muchos números (el texto extraído queda desordenado) | INDEC, "Índice de precios al consumidor (IPC). Octubre de 2024". Licencia Creative Commons: se permite su reproducción con atribución de la fuente. |
| `irs_form_w9.pdf` | 6 | en | Pregunta en español sobre un documento en inglés | IRS, Form W-9 (Rev. March 2024). Obra del gobierno de EE. UU., dominio público. |
| `pdfjs_wikipedia.pdf` | 1 | en | Documento corto en inglés (pocos fragmentos: el top 5 trae casi todo) | Artículo "PDF.js" de Wikipedia en inglés. [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). |

Se descartaron papers de arXiv y de ACM (su licencia no permite redistribuirlos), libros de más de 300 páginas (la app los rechaza) y los PDFs de la suite de pruebas de pdf.js, que sirven para casos borde del parser pero casi no tienen contenido para preguntar.
