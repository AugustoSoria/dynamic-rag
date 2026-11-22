/**
 * Parser incremental de Server-Sent Events.
 *
 * Los datos llegan de la red en pedazos arbitrarios: un evento puede venir partido en varios
 * pedazos, o varios eventos en uno solo. El parser acumula el texto y emite cada evento completo
 * (bloque terminado en línea en blanco) con su nombre y su `data` ya parseado como JSON.
 */
export type SSEHandler = (event: string, data: unknown) => void;

export function createSSEParser(onEvent: SSEHandler) {
  let buffer = "";

  const dispatch = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
      // Las líneas que empiezan con ":" son comentarios (p. ej. keep-alive) y se ignoran.
    }
    if (dataLines.length > 0) onEvent(event, JSON.parse(dataLines.join("\n")));
  };

  const drain = () => {
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      dispatch(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
    }
  };

  return {
    push(chunk: string) {
      buffer += chunk;
      // Normalizamos los fines de línea, pero si el pedazo termina en "\r" lo dejamos pendiente:
      // puede ser la primera mitad de un "\r\n" cuyo "\n" llega en el próximo pedazo.
      const pendingCR = buffer.endsWith("\r");
      if (pendingCR) buffer = buffer.slice(0, -1);
      buffer = buffer.replace(/\r\n?/g, "\n");
      drain();
      if (pendingCR) buffer += "\r";
    },
    /** Al cerrarse el stream: procesa lo que haya quedado sin la línea en blanco final. */
    end() {
      buffer = buffer.replace(/\r\n?/g, "\n");
      drain();
      if (buffer.trim()) dispatch(buffer);
      buffer = "";
    },
  };
}
