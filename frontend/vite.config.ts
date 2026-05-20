import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
// No proxy — the frontend calls the backend directly at http://localhost:8000.
// CORS on the backend explicitly allows http://localhost:5173 (Vite dev).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
});
