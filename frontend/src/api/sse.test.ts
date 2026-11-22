import { describe, expect, it } from "vitest";

import { createSSEParser } from "./sse";

function collect() {
  const events: Array<[string, unknown]> = [];
  const parser = createSSEParser((event, data) => events.push([event, data]));
  return { events, parser };
}

describe("createSSEParser", () => {
  it("parsea eventos completos", () => {
    const { events, parser } = collect();
    parser.push('event: token\ndata: {"text": "Hola"}\n\nevent: done\ndata: {}\n\n');
    expect(events).toEqual([
      ["token", { text: "Hola" }],
      ["done", {}],
    ]);
  });

  it("arma un evento que llega partido en varios pedazos", () => {
    const { events, parser } = collect();
    for (const piece of ["event: tok", 'en\ndata: {"te', 'xt": "a"}\n', "\n"]) parser.push(piece);
    expect(events).toEqual([["token", { text: "a" }]]);
  });

  it("no emite nada hasta que llega la línea en blanco final", () => {
    const { events, parser } = collect();
    parser.push('event: token\ndata: {"text": "a"}\n');
    expect(events).toEqual([]);
    parser.push("\n");
    expect(events).toHaveLength(1);
  });

  it("acepta fines de línea \\r\\n, incluso partidos entre dos pedazos", () => {
    const { events, parser } = collect();
    parser.push('event: token\r\ndata: {"text": "a"}\r');
    parser.push("\n\r");
    parser.push("\n");
    expect(events).toEqual([["token", { text: "a" }]]);
  });

  it("respeta saltos de línea y caracteres especiales dentro del JSON", () => {
    const { events, parser } = collect();
    parser.push('event: token\ndata: {"text": "línea 1\\nlínea 2 [1] **ñ**"}\n\n');
    expect(events).toEqual([["token", { text: "línea 1\nlínea 2 [1] **ñ**" }]]);
  });

  it("ignora comentarios (keep-alive)", () => {
    const { events, parser } = collect();
    parser.push(": ping\n\nevent: done\ndata: {}\n\n");
    expect(events).toEqual([["done", {}]]);
  });

  it("end() procesa un último evento sin línea en blanco final", () => {
    const { events, parser } = collect();
    parser.push("event: done\ndata: {}");
    expect(events).toEqual([]);
    parser.end();
    expect(events).toEqual([["done", {}]]);
  });
});
