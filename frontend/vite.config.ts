import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server proxies /api to the FastAPI backend, so the app uses same-origin URLs
// locally and in a future single-domain deployment.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
