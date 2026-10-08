import { defineConfig } from "@playwright/test";

/**
 * Razorpay's CSP, proved by the browser against its live Checkout script
 * (T-8.7; razorpay-csp.spec.ts says how). By hand only: it needs the internet,
 * and no build, so it isn't in playwright.config.ts beside the benchmarks.
 *
 *     cd web && pnpm exec playwright test -c bench/razorpay-csp.config.ts
 */
export default defineConfig({
  testDir: ".",
  testMatch: "razorpay-csp.spec.ts",
  workers: 1,
  retries: 0,
  reporter: "list",
  timeout: 120_000,
  use: { trace: "off", video: "off", screenshot: "off" },
});
