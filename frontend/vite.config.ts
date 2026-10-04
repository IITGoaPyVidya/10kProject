import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies /api to the backend so the browser stays same-origin (no CORS needed).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
});
