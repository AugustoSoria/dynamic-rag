export const CITATION_HREF = "#cite-";

/**
 * Citas que puede escribir el modelo:
 *   [1]          el formato que pide el prompt
 *   【1】         el formato nativo de gpt-oss (corchetes lenticulares), que a veces usa igual
 *   【1†L3-L5】   variante del formato nativo con una referencia interna después de "†"
 * No toma "[1](url)": eso ya es un link de Markdown.
 */
const CITATION_RE = /[[【](\d{1,2})(?:†[^\]】]*)?[\]】](?!\()/g;

/** Convierte las citas en links internos de Markdown (`[1](#cite-1)`) para renderizarlas como chips. */
export function linkCitations(text: string): string {
  return text.replace(CITATION_RE, (_, n) => `[${n}](${CITATION_HREF}${n})`);
}
