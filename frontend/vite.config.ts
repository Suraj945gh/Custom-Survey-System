import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

declare const process: { env: Record<string, string | undefined> };
// Where the Python API runs. Change it with:  API_TARGET=http://127.0.0.1:9000 npm run dev
const apiTarget = process.env.API_TARGET ?? "http://127.0.0.1:8000";

// The frontend runs on :5173 and forwards every /api call to the Python backend on :8000.
// host: true lets a phone on the same Wi-Fi open http://<this computer's IP>:5173
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": apiTarget },
    fs: { allow: [".."] }, // lets the upload page offer the files in /samples as examples
  },
  preview: { host: true, port: 5173, proxy: { "/api": apiTarget } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: false,
  },
});
