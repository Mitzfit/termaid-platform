import { defineConfig } from "vite";

// Dev server proxies API + WS to the FastAPI backend on :8000, so the
// frontend runs on :5173 with hot-reload and no CORS headaches.
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
