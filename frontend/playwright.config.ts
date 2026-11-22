import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

const BACKEND_DIR = path.resolve(import.meta.dirname, "../backend");
// Python del venv del backend (en Windows está en Scripts\, en Linux/macOS en bin/).
export const PYTHON =
  process.platform === "win32"
    ? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
    : path.join(BACKEND_DIR, ".venv", "bin", "python");

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  outputDir: "./e2e-results/artifacts",
  reporter: [
    ["list"],
    ["html", { outputFolder: "./e2e-results/report", open: "never" }],
    ["json", { outputFile: "./e2e-results/results.json" }], // incluye las anotaciones (respuestas del LLM)
  ],

  // De a uno: todos comparten el backend y la cuota de Groq, y así los videos son fáciles de seguir.
  workers: 1,
  fullyParallel: false,
  timeout: 120_000, // las respuestas del LLM pueden tardar
  expect: { timeout: 15_000 },

  use: {
    baseURL: "http://localhost:5173",
    viewport: { width: 1440, height: 900 },
    video: { mode: "on", size: { width: 1440, height: 900 } },
    screenshot: "on",
    trace: "retain-on-failure",
    // Un poco más lento que un humano apurado, para que los videos se puedan seguir.
    launchOptions: { slowMo: 120 },
  },

  projects: [
    {
      name: "desktop",
      testIgnore: /mobile\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "mobile",
      testMatch: /mobile\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
        video: { mode: "on", size: { width: 390, height: 844 } },
      },
    },
  ],

  webServer: [
    {
      command: `"${PYTHON}" -m uvicorn app.main:app --port 8000`,
      cwd: BACKEND_DIR,
      url: "http://localhost:8000/api/health",
      reuseExistingServer: true,
      timeout: 180_000, // la primera vez carga el modelo de embeddings
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
