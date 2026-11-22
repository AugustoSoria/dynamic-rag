import { describe, expect, it } from "vitest";

import { escapeHtml, findHighlightedItems } from "./highlight";

// Simula los items de texto que devuelve pdf.js: una línea por item, con items vacíos de fin de línea.
const items = [
  { str: "Historia" },
  { str: "" },
  { str: "La empresa Acme fue funda-" },
  { str: "da en 1998 en Córdoba por Ana Pérez." },
  { str: "Durante los primeros años reparó" },
  { str: "electrodomésticos." },
  { type: "beginMarkedContent" }, // TextMarkedContent: sin texto
  { str: "Productos" },
  { str: "En 2020 lanzó el robot Zeta." },
];

describe("findHighlightedItems", () => {
  it("marca las líneas del fragmento aunque el backend haya limpiado espacios y guiones", () => {
    // Así llega el chunk desde el backend: la palabra cortada con guion ya está unida.
    const chunk =
      "La empresa Acme fue fundada en 1998 en Córdoba por Ana Pérez.\nDurante los primeros años reparó electrodomésticos.";
    expect([...findHighlightedItems(items, chunk)].sort()).toEqual([2, 3, 4, 5]);
  });

  it("no marca nada si el fragmento no está en la página", () => {
    expect(findHighlightedItems(items, "Un texto que no aparece en esta página para nada").size).toBe(0);
  });

  it("usa el final del fragmento si el principio no coincide, sin pasarse del final", () => {
    const chunk =
      "TEXTO EXTRA QUE NO ESTÁ EN LA PÁGINA, AGREGADO AL PRINCIPIO DEL FRAGMENTO PARA QUE EL ANCLA INICIAL FALLE " +
      "La empresa Acme fue fundada en 1998 en Córdoba por Ana Pérez. Durante los primeros años reparó electrodomésticos.";
    const result = findHighlightedItems(items, chunk);
    expect(result.has(3)).toBe(true);
    expect(result.has(8)).toBe(false);
  });

  it("encuentra el fragmento aunque un lado tenga ligaduras tipográficas (ﬁ, ﬂ) y el otro no", () => {
    const pdfjsItems = [{ str: "A Company Profile" }, { str: "The first paragraph." }];
    // Así llega el chunk desde PyMuPDF: con los caracteres de ligadura.
    const chunk = "A Company Proﬁle\nThe ﬁrst paragraph.";
    expect([...findHighlightedItems(pdfjsItems, chunk)]).toEqual([0, 1]);
  });

  it("es insensible a mayúsculas", () => {
    expect([...findHighlightedItems(items, "EN 2020 LANZÓ EL ROBOT ZETA.")]).toEqual([8]);
  });

  it("devuelve vacío con un fragmento vacío", () => {
    expect(findHighlightedItems(items, "   ").size).toBe(0);
  });
});

describe("escapeHtml", () => {
  it("escapa los caracteres que romperían el HTML de la capa de texto", () => {
    expect(escapeHtml('<script>alert("x")</script> & más')).toBe('&lt;script&gt;alert("x")&lt;/script&gt; &amp; más');
  });
});
