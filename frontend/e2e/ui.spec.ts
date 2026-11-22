/**
 * Casos de interfaz y validaciones. No llaman al LLM: se pueden correr seguido sin gastar cuota de Groq.
 * Cada test arranca con un navegador limpio, o sea, con una sesión nueva.
 */
import { writeFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { linger, pdf, uploadExpectingError, uploadPdf } from "./helpers";

test.beforeEach(async ({ page }) => {
  page.on("dialog", (dialog) => dialog.accept()); // confirmaciones de borrar / nueva sesión
  await page.goto("/");
  await expect(page.getByText(/Hasta \d+ MB/)).toBeVisible(); // la config del backend cargó
});

test("rechaza archivos inválidos con un mensaje claro", async ({ page }, testInfo) => {
  const txt = testInfo.outputPath("notas.txt");
  writeFileSync(txt, "esto no es un pdf");

  await uploadExpectingError(page, txt, /Solo se aceptan archivos PDF/);
  await linger(page);
  await uploadExpectingError(page, pdf("sin_texto.pdf"), /no tiene texto extraíble/);
  await linger(page);
  await uploadExpectingError(page, pdf("con_contrasena.pdf"), /protegido con contraseña/);
  await linger(page);
  await uploadExpectingError(page, pdf("301_paginas.pdf"), /301 páginas; el máximo es 300/);
  await linger(page);

  await expect(page.getByTestId("document-item")).toHaveCount(0);
});

test("cuenta las páginas en blanco en el total", async ({ page }) => {
  await uploadPdf(page, "con_paginas_en_blanco.pdf");
  await expect(page.getByTestId("document-item")).toContainText("5 páginas");
  await linger(page);
});

test("bloquea la subida al llegar al máximo de documentos", async ({ page }) => {
  await uploadPdf(page, "informe_acme.pdf");
  await uploadPdf(page, "receta_empanadas.pdf");
  await uploadPdf(page, "tabla_de_precios.pdf");

  const zone = page.getByRole("button", { name: /Máximo de 3 documentos alcanzado/ });
  await expect(zone).toBeVisible();
  await expect(zone).toBeDisabled();
  await linger(page);
});

test("abre un documento en el visor y navega sus páginas", async ({ page }) => {
  await uploadPdf(page, "informe_acme.pdf");
  await page.getByRole("button", { name: /^informe_acme\.pdf/ }).click();

  const viewer = page.getByTestId("pdf-viewer");
  await expect(viewer).toContainText("1 / 4");
  await expect(viewer.getByText("Informe anual de Acme")).toBeVisible();
  await linger(page);

  await viewer.getByRole("button", { name: "Página siguiente" }).click();
  await expect(viewer).toContainText("2 / 4");
  await expect(viewer.getByText("Historia")).toBeVisible();
  await linger(page);

  await viewer.getByRole("button", { name: "Cerrar visor" }).click();
  await expect(viewer).toBeHidden();
});

test("elimina un documento", async ({ page }) => {
  await uploadPdf(page, "receta_empanadas.pdf");
  await page.getByTestId("document-item").hover();
  await page.getByRole("button", { name: "Eliminar receta_empanadas.pdf" }).click();

  await expect(page.getByText("Todavía no subiste ningún documento.")).toBeVisible();
  await linger(page);
});

test("una sesión nueva empieza vacía", async ({ page }) => {
  await uploadPdf(page, "receta_empanadas.pdf");
  await page.getByRole("button", { name: "Nueva sesión" }).click();

  await expect(page.getByText("Todavía no subiste ningún documento.")).toBeVisible();
  await linger(page);
});

test("muestra un error entendible si el backend no responde, y se recupera", async ({ page }) => {
  // Simulamos el backend caído para la lista de documentos (lo que devuelve un proxy cuando no hay backend).
  await page.route("**/api/documents", (route) => route.fulfill({ status: 502, body: "Bad Gateway" }));
  await page.reload();

  await expect(page.getByText("No se pudieron cargar tus documentos.")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/No se pudo conectar con el servidor/)).toBeVisible();
  await linger(page);

  await page.unroute("**/api/documents");
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByText("Todavía no subiste ningún documento.")).toBeVisible();
  await linger(page);
});
