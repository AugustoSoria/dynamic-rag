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

  // Buscamos el inicio del chunk con un "ancla" corta; si no aparece, probamos con una del medio.
  let start = page.indexOf(needle.slice(0, ANCHOR_LENGTH));
  if (start === -1 && needle.length > ANCHOR_LENGTH * 2) {
    const mid = Math.floor(needle.length / 2);
    const found = page.indexOf(needle.slice(mid, mid + ANCHOR_LENGTH));
    if (found !== -1) start = Math.max(0, found - mid);
  }
  if (start === -1) return result;

  const end = start + needle.length;
  for (const r of ranges) {
    if (r.to > start && r.from < end) result.add(r.index);
  }
  return result;
}

export function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
