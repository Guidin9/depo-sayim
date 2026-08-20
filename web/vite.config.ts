import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Derleme çıktısı doğrudan FastAPI'nin servis ettiği app/static klasörüne gider.
// Hiçbir varlık CDN'den çekilmez; depodaki laptopta internet olmayabilir.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../app/static",
    emptyOutDir: true,
    assetsInlineLimit: 0,
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
