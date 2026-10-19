/**
 * The server's errors to Sentry (T-9.12), on builds that report only
 * (sentry-config.ts): Next calls `register` once as a server starts, and
 * `onRequestError` with each error a Server Component, route handler or the
 * proxy throws. Each tests the inlined `SENTRY_WEB_CONFIG` itself, as
 * instrumentation-client.ts does, so a local or ci build drops the SDK's
 * import. Node's runtime only: the proxy runs on it in Next 16, and nothing
 * here uses the edge's.
 */

import type { Instrumentation } from "next";

import { sentryConfig } from "./lib/sentry-config";

export async function register(): Promise<void> {
  if (process.env.SENTRY_WEB_CONFIG && process.env.NEXT_RUNTIME === "nodejs") {
    const config = sentryConfig(process.env.SENTRY_WEB_CONFIG);
    if (config === null) return;
    const { startSentry } = await import("./lib/sentry");
    startSentry(config, "server");
  }
}

export const onRequestError: Instrumentation.onRequestError = async (
  ...args
) => {
  if (process.env.SENTRY_WEB_CONFIG && process.env.NEXT_RUNTIME === "nodejs") {
    if (sentryConfig(process.env.SENTRY_WEB_CONFIG) === null) return;
    const { captureRequestError } = await import("./lib/sentry");
    captureRequestError(...args);
  }
};
