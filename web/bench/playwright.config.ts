import { defineConfig } from "@playwright/test";

/**
 * Benchmarks run by hand, never in `make test` or CI (as `api/bench`):
 *
 *     cd web && pnpm exec playwright test -c bench
 *
 * A production build, served on a port of its own; the API is answered by
 * each benchmark itself, so nothing else need be running.
 */
export const WEB = "http://127.0.0.1:3199";
export const API = "http://127.0.0.1:8199";

export default defineConfig({
  testDir: ".",
  workers: 1,
  retries: 0,
  reporter: "list",
  timeout: 900_000,
  use: {
    baseURL: WEB,
    trace: "off",
    video: "off",
    screenshot: "off",
  },
  webServer: {
    command: "pnpm build && pnpm start --port 3199",
    url: `${WEB}/login`,
    env: { APP_ENV: "local", NEXT_PUBLIC_API_URL: API },
    reuseExistingServer: false,
    timeout: 300_000,
  },
});
