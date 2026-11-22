import path from "node:path";

import { expect, type Locator, type Page } from "@playwright/test";

export const PDFS_DIR = path.resolve(import.meta.dirname, "../../backend/test_pdfs");
export const pdf = (name: string) => path.join(PDFS_DIR, name);

/** Pausa breve para que el resultado quede visible en el video. */
export const linger = (page: Page, ms = 1500) => page.waitForTimeout(ms);

/** Sube un PDF y espera a que aparezca en la lista. */
export async function uploadPdf(page: Page, name: string) {
  await page.locator('input[type="file"]').setInputFiles(pdf(name));
  await expect(page.getByTestId("document-item").filter({ hasText: name })).toBeVisible({ timeout: 60_000 });
}

/** Sube un archivo que el backend debería rechazar y devuelve el mensaje de error mostrado. */
export async function uploadExpectingError(page: Page, filePath: string, expected: RegExp) {
  await page.locator('input[type="file"]').setInputFiles(filePath);
  await expect(page.getByText(expected)).toBeVisible({ timeout: 60_000 });
}

/**
 * Hace una pregunta y espera a que la respuesta termine de llegar.
 * Devuelve el mensaje del asistente (para inspeccionar texto, citas y fuentes).
 */
export async function ask(page: Page, question: string): Promise<Locator> {
  const before = await page.getByTestId("assistant-message").count();
  await page.getByRole("textbox").fill(question);
  await page.keyboard.press("Enter");

  const answer = page.getByTestId("assistant-message").nth(before);
  await expect(answer).toHaveAttribute("data-status", /done|error/, { timeout: 90_000 });
  await expect(answer).toHaveAttribute("data-status", "done");
  return answer;
}

/**
 * Texto de la respuesta, sin la sección de fuentes.
 * gpt-oss a veces usa espacios tipográficos (U+202F, U+00A0, U+2009) entre nombres o en números
 * ("Ana Pérez", "50 000"): los normalizamos a espacios comunes para poder comparar.
 */
export async function answerText(answer: Locator): Promise<string> {
  const text = await answer.locator(".markdown").innerText();
  return text.replace(/[   ]/g, " ").trim();
}

/** Abre la lista de fuentes de una respuesta y devuelve los nombres de archivo citados. */
export async function sourceFilenames(answer: Locator): Promise<string[]> {
  await answer.getByRole("button", { name: /fuentes?$/ }).click();
  return answer.getByTitle("Ver en el documento").locator("span.truncate").allInnerTexts();
}
