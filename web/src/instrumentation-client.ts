/**
 * The browser's errors to Sentry (T-9.12), on builds that report only
 * (sentry-config.ts). `SENTRY_WEB_CONFIG` is written into the bundle at build
 * time, so on a local or ci build the test below reads `if ("")`: the bundler
 * drops the block, its import with it, and the SDK isn't in that build at all.
 * The test is on the inlined string itself, never a function's result, which
 * the bundler can't see through. Where it reports, the SDK is fetched after
 * the page's own code, never in its way.
 */

import { sentryConfig } from "./lib/sentry-config";

if (process.env.SENTRY_WEB_CONFIG) {
  const config = sentryConfig(process.env.SENTRY_WEB_CONFIG);
  if (config !== null) {
    void import("./lib/sentry").then(({ startSentry }) =>
      startSentry(config, "browser"),
    );
  }
}
