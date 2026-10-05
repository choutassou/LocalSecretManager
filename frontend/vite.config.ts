import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build output goes to ../static, which server.py serves.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "../static", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
