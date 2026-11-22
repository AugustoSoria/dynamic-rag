/**
 * Encuentra qué trozos de texto de una página de pdf.js corresponden a un fragmento (chunk) citado.
 *
 * El texto del chunk pasó por la limpieza del backend (espacios colapsados, palabras cortadas con guion
 * unidas), así que no coincide carácter a carácter con el texto crudo de pdf.js. Para comparar,
 * normalizamos ambos lados quitando espacios y guiones, y trabajamos con offsets sobre ese texto normalizado.
 */

const STRIP_RE = /[\s\-­‐‑]+/g; // espacios, guiones y soft hyphen
const ANCHOR_LENGTH = 40;

function normalize(text: string): string {
  return text.replace(STRIP_RE, "").toLowerCase();
}

/** Items de pdf.js: los TextItem tienen `str`; los TextMarkedContent (marcas de estructura) no. */
export type TextItemLike = object;

function itemText(item: TextItemLike): string {
  return "str" in item && typeof item.str === "string" ? item.str : "";
}

export function findHighlightedItems(items: readonly TextItemLike[], chunkText: string): Set<number> {
  const result = new Set<number>();
  const needle = normalize(chunkText);
  if (!needle) return result;

  // Texto normalizado de la página + rango [from, to) que ocupa cada item.
  const ranges: Array<{ index: number; from: number; to: number }> = [];
  let page = "";
  items.forEach((item, index) => {
    const norm = normalize(itemText(item));
    if (!norm) return;
    ranges.push({ index, from: page.length, to: page.length + norm.length });
    page += norm;
  });

  const span = locate(page, needle);
  if (!span) return result;

  const [start, end] = span;
  for (const r of ranges) {
    if (r.to > start && r.from < end) result.add(r.index);
  }
  return result;
}

/**
 * Ubica el fragmento en el texto de la página con "anclas" cortas, por si el texto no coincide entero.
 * Cada ancla fija el extremo que tiene más cerca; el otro se estima con el largo del fragmento.
 */
function locate(page: string, needle: string): [number, number] | null {
  const len = needle.length;

  // 1. Ancla al inicio: fija el comienzo.
  const head = page.indexOf(needle.slice(0, ANCHOR_LENGTH));
  if (head !== -1) return [head, head + len];

  // 2. Ancla al final: fija el final.
  const tail = needle.slice(-ANCHOR_LENGTH);
  const tailAt = page.indexOf(tail);
  if (tailAt !== -1) {
    const end = tailAt + tail.length;
    return [Math.max(0, end - len), end];
  }

  // 3. Ancla en el medio: ambos extremos se calculan desde ella (no desde un inicio ya recortado,
  //    que correría el final más allá de donde termina el fragmento).
  if (len > ANCHOR_LENGTH * 2) {
    const mid = Math.floor(len / 2);
    const midAt = page.indexOf(needle.slice(mid, mid + ANCHOR_LENGTH));
    if (midAt !== -1) return [Math.max(0, midAt - mid), midAt + (len - mid)];
  }
  return null;
}

export function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
