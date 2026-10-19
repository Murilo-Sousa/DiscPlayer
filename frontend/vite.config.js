import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em desenvolvimento, o Vite (porta 5173) repassa /api para o Flask (porta 5000).
// Assim o navegador enxerga uma única origem e o cookie de sessão funciona sem CORS.
const backend = process.env.VITE_BACKEND_URL || "http://127.0.0.1:5000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
