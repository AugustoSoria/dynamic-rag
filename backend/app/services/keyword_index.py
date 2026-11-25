"""
Búsqueda por palabras clave (BM25), para combinar con la semántica.

La búsqueda por embeddings encuentra textos de significado parecido, pero falla con referencias exactas
("artículo 14"), números y nombres propios. BM25 puntúa por coincidencia de palabras, dando más peso a las
palabras raras del corpus.

El índice de cada sesión se arma con los textos que ya guarda Chroma (no hay otra copia en disco, así que
sobrevive a los reinicios) y se cachea en memoria hasta que se agrega o borra un documento de la sesión.
"""

import math
import re
import threading
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

# Parámetros estándar de BM25: saturación de la frecuencia (k1) y normalización por largo del texto (b).
K1 = 1.5
B = 0.75

# Palabras demasiado frecuentes para aportar a la búsqueda (sin tildes, como quedan tras normalizar).
STOPWORDS = frozenset(
    """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun como con contra cual cuales cuando
    cuanto cuanta cuantos cuantas de del desde donde dos e el ella ellas ellos en entre era eran es esa esas ese
    eso esos esta estan estas este esto estos fue fueron ha han hasta hay la las le les lo los mas me mi mis muy
    ni no nos o otra otras otro otros para pero por porque que quien quienes se segun ser si sin sobre son su
    sus tambien tiene tienen todo todos tu tus un una unas uno unos y ya yo dice dicen decir hace documento
    the of and or to in on at by for with from as is are was were be been it its this that these those which
    what who whom how when where why do does did an not no can will would should may might
    """.split()
)

# Abreviaturas que en los documentos aparecen de una forma y en las preguntas de otra.
ALIASES = {"articulo": "art", "articulos": "art", "arts": "art", "inciso": "inc", "incisos": "inc"}

# Números con separadores ("2.948,01", "193,0") como un solo token; si no, palabras.
_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)*|[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Minúsculas, sin tildes, sin palabras vacías y con las abreviaturas unificadas."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    tokens = (ALIASES.get(t, t) for t in _TOKEN_RE.findall(text))
    return [t for t in tokens if t not in STOPWORDS]


@dataclass
class IndexedChunk:
    id: str
    doc_id: str
    text: str


class _Bm25:
    def __init__(self, chunks: list[IndexedChunk]):
        self.ids = [c.id for c in chunks]
        self.doc_ids = [c.doc_id for c in chunks]
        self.term_freqs = [Counter(tokenize(c.text)) for c in chunks]
        self.lengths = [sum(tf.values()) for tf in self.term_freqs]
        self.avg_length = sum(self.lengths) / len(chunks) if chunks else 0
        doc_freq = Counter(term for tf in self.term_freqs for term in tf)
        n = len(chunks)
        # IDF de BM25 en la variante que nunca es negativa (la de Lucene).
        self.idf = {term: math.log(1 + (n - df + 0.5) / (df + 0.5)) for term, df in doc_freq.items()}

    def search(self, query: str, k: int, doc_ids: list[str] | None) -> list[str]:
        terms = [t for t in set(tokenize(query)) if t in self.idf]
        if not terms:
            return []
        allowed = set(doc_ids) if doc_ids else None
        scored = []
        for i, tf in enumerate(self.term_freqs):
            if allowed is not None and self.doc_ids[i] not in allowed:
                continue
            norm = K1 * (1 - B + B * self.lengths[i] / self.avg_length)
            score = sum(self.idf[t] * tf[t] * (K1 + 1) / (tf[t] + norm) for t in terms if tf[t])
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda s: s[0], reverse=True)
        return [self.ids[i] for _, i in scored[:k]]


_indexes: dict[str, _Bm25] = {}
# Cuántas veces se invalidó cada sesión: evita guardar un índice armado con datos que cambiaron mientras tanto.
_versions: Counter[str] = Counter()
_lock = threading.Lock()


def search(
    session_id: str, query: str, k: int, doc_ids: list[str] | None, load: Callable[[], list[IndexedChunk]]
) -> list[str]:
    """Ids de los k fragmentos con mejor puntaje BM25. `load` trae los fragmentos de la sesión si no hay índice."""
    with _lock:
        index = _indexes.get(session_id)
        version = _versions[session_id]
    if index is None:
        # Se arma fuera del lock: con miles de fragmentos tarda un poco y no debe frenar otras sesiones.
        index = _Bm25(load())
        with _lock:
            # Si se agregó o borró un documento mientras se armaba, este índice ya está viejo: se usa
            # para esta búsqueda pero no se guarda, y la próxima lo arma de nuevo.
            if _versions[session_id] == version:
                _indexes[session_id] = index
    return index.search(query, k, doc_ids)


def invalidate(session_id: str) -> None:
    """
    Descarta el índice de la sesión: se vuelve a armar en la próxima búsqueda. Se llama también al borrar
    la sesión; el contador queda (un entero por sesión, se libera al reiniciar), porque borrarlo permitiría
    guardar un índice viejo que se estuviera armando en ese momento.
    """
    with _lock:
        _indexes.pop(session_id, None)
        _versions[session_id] += 1
