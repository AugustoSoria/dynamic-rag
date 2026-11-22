import { execFileSync } from "node:child_process";
import path from "node:path";

import { PYTHON } from "../playwright.config";

/** Genera los PDFs de prueba (backend/test_pdfs) antes de correr los tests. */
export default function globalSetup() {
  const backendDir = path.resolve(import.meta.dirname, "../../backend");
  execFileSync(PYTHON, ["-W", "ignore", "scripts/make_test_pdfs.py"], { cwd: backendDir, stdio: "inherit" });
}
