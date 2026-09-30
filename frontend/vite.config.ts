import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Le front appelle /api/... ; en développement, Vite relaie vers FastAPI (port 8000) :
// même origine pour le navigateur, pas de CORS, et le flux SSE du chat passe tel quel.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // Bibliothèques lourdes dans des fichiers séparés : meilleur cache navigateur.
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return undefined;
          if (/[\\/](echarts|zrender|echarts-for-react)[\\/]/.test(id)) return "echarts";
          if (/[\\/]ag-grid-/.test(id)) return "aggrid";
          if (/[\\/]@mantine[\\/]/.test(id)) return "mantine";
          return undefined;
        },
      },
    },
  },
});
