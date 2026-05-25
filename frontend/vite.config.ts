/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vitejs.dev/config/
// No proxy — the frontend calls the backend directly at http://localhost:8000.
// CORS on the backend explicitly allows http://localhost:5173 (Vite dev).
export default defineConfig({
  // Tailwind v4 ships its own Vite plugin — no PostCSS config needed. The
  // utility classes are pulled from any file under src/ that imports them.
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  // vitest config lives next to vite config so React + path resolution stay
  // identical between dev/build and tests. jsdom gives us a DOM for component
  // render tests; setup.ts registers @testing-library/jest-dom matchers.
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
