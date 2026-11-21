import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // En desarrollo el frontend llama a /api/* en su mismo origen y Vite lo reenvía al backend:
    // así no hace falta configurar CORS localmente.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
