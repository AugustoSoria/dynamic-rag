/** Layout de celular. Corre en el proyecto "mobile" de playwright.config.ts (pantalla de 390x844). */
import { expect, test } from "@playwright/test";

import { linger, uploadPdf } from "./helpers";

test("menú lateral y visor a pantalla completa", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Abrir documentos" }).click();
  await uploadPdf(page, "informe_acme.pdf");
  await linger(page, 800);

  await page.getByRole("button", { name: /^informe_acme\.pdf/ }).click();
  const viewer = page.getByTestId("pdf-viewer");
  await expect(viewer).toBeVisible();
  await expect(viewer.getByText("Informe anual de Acme")).toBeVisible();
  // A pantalla completa: ocupa todo el ancho.
  expect((await viewer.boundingBox())?.width).toBeGreaterThanOrEqual(380);
  await linger(page);
});
