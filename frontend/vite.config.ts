import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  optimizeDeps: {
    // react-pdf solo se importa desde el visor, que se carga con lazy(). Sin esto, en desarrollo Vite
    // lo descubre recién al abrir el primer PDF y recarga la página entera (se pierde el chat).
    include: ["react-pdf"],
  },
  server: {
    // En desarrollo el frontend llama a /api/* en su mismo origen y Vite lo reenvía al backend:
    // así no hace falta configurar CORS localmente.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
