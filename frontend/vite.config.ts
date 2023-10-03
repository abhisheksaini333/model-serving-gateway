import { defineConfig } from "vitest/config";
export default defineConfig({
  server: { proxy: { "/ops": "http://127.0.0.1:8093", "/v1": "http://127.0.0.1:8093", "/health": "http://127.0.0.1:8093" } },
  test: { environment: "jsdom", include: ["tests/**/*.test.tsx"], threads: false },
});
