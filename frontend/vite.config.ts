import { defineConfig } from "vite";

// Dev server proxies API + WS to the FastAPI backend on :8000, so the
// frontend runs on :5173 with hot-reload and no CORS headaches.
//
// clearScreen/strictPort/watch.ignored are the standard Tauri+Vite pairing:
// Tauri's own CLI output needs to stay visible (clearScreen: false), Tauri
// expects the dev server on exactly the port in tauri.conf.json's devUrl
// (strictPort), and without the ignore, Vite's file watcher walks into
// src-tauri/target/ and throws EBUSY on binaries cargo is actively writing.
export default defineConfig({
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    watch: { ignored: ["**/src-tauri/**"] },
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
