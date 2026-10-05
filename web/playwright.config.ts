import { copyFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { defineConfig, devices } from "@playwright/test";

/**
 * The E2E (T-3.13, 06-TESTING): a production build of the web against the API
 * on a P-55 slot of its own (api/tests/e2e_server.py, with the worker beside
 * it and the local S3 behind it, T-4.9), on ports apart from `make dev`'s.
 * One worker: the fake SMS's outbox lives in the API's one process, and the
 * journeys share its rate-limit windows.
 */
const API = "http://127.0.0.1:8100";
const WEB = "http://127.0.0.1:3100";

/**
 * The fake camera (T-4.9, D-330): Chromium plays a file instead of a camera,
 * and J2's selfie is its frames. The file is NASA's 2017 portrait of Raja
 * Chari (api/tests/fixtures/faces, public domain), copied at load as a
 * one-frame MJPEG, which Chromium's file camera reads by its extension (Y4M
 * or MJPEG). J2's profile photo is his 2021 portrait, so the real models
 * (D-088) are given two photos of one person to match. Nothing is committed
 * for it: the copy is remade at every load.
 */
const CAMERA_PORTRAIT = resolve(
  __dirname,
  "../api/tests/fixtures/faces/chari_2017.jpg",
);
const CAMERA = join(tmpdir(), "velora-e2e-camera.mjpeg");
copyFileSync(CAMERA_PORTRAIT, CAMERA);

/**
 * Chromium, the full build in its new headless mode, not Playwright's headless
 * shell: the shell has no media capture, and `getUserMedia` there is
 * "NotSupportedError: Not supported" (seen 5 October 2026), so J2's camera
 * can't open. `playwright install chromium` installs both.
 */
const chromium = {
  ...devices["Desktop Chrome"],
  channel: "chromium",
  launchOptions: {
    args: [
      "--use-fake-device-for-media-stream",
      `--use-file-for-fake-video-capture=${CAMERA}`,
    ],
  },
};

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
        ...chromium,
        viewport: { width: 390, height: 844 },
      },
    },
    {
      name: "desktop",
      use: {
        ...chromium,
        viewport: { width: 1280, height: 800 },
      },
    },
    // Decision 2: Firefox, run once locally (`E2E_FIREFOX=1 make e2e`), never
    // in CI. The fake camera above is Chromium's, so J2 skips itself there.
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
