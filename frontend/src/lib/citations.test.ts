import { describe, expect, it } from "vitest";

import { linkCitations } from "./citations";

describe("linkCitations", () => {
  it("convierte citas con corchetes comunes", () => {
    expect(linkCitations("Dato [1] y otro [2][3].")).toBe("Dato [1](#cite-1) y otro [2](#cite-2)[3](#cite-3).");
  });

  it("convierte el formato nativo de gpt-oss 【n】", () => {
    expect(linkCitations("Ana Pérez y Luis Gómez【1】.")).toBe("Ana Pérez y Luis Gómez[1](#cite-1).");
  });

  it("convierte la variante 【n†...】", () => {
    expect(linkCitations("Dato【2†L3-L5】.")).toBe("Dato[2](#cite-2).");
  });

  it("no toca links de Markdown ni corchetes que no son citas", () => {
    const text = "Ver [1](https://ejemplo.com), la lista [a] y el año [2023].";
    expect(linkCitations(text)).toBe(text);
  });
});
