import { defineConfig, devices } from "@playwright/test";

/**
 * The E2E (T-3.13, 06-TESTING): a production build of the web against the API
 * on a P-55 slot of its own (api/tests/e2e_server.py), on ports apart from
 * `make dev`'s. One worker: the fake SMS's outbox lives in the API's one
 * process, and the journeys share its rate-limit windows.
 */
const API = "http://127.0.0.1:8100";
const WEB = "http://127.0.0.1:3100";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: "list",
  timeout: 120_000,
  use: {
    baseURL: WEB,
    // Decision 22: nothing kept. A trace records request and response bodies
    // (numbers, codes, access tokens), and a screenshot of the phone screen
    // shows the number. Failures speak through their assertions.
    trace: "off",
    video: "off",
    screenshot: "off",
  },
  projects: [
    {
      name: "mobile",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
      },
    },
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
    // Decision 2: Firefox, run once locally (`E2E_FIREFOX=1 make e2e`), never in CI.
    ...(process.env.E2E_FIREFOX === "1"
      ? [{ name: "firefox", use: { ...devices["Desktop Firefox"] } }]
      : []),
  ],
  webServer: [
    {
      command: "uv run python -m tests.e2e_server",
      cwd: "../api",
      url: `${API}/healthz`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      command: "pnpm build && pnpm start --port 3100",
      url: `${WEB}/login`,
      env: { APP_ENV: "local", NEXT_PUBLIC_API_URL: API },
      reuseExistingServer: false,
      timeout: 300_000,
    },
  ],
});
