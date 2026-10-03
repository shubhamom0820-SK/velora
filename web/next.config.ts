import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

import { assertKnownAppEnv } from "./src/lib/build-env";
import { securityHeaders } from "./src/lib/security-headers";

export const nextConfig: NextConfig = {
  // `next dev` otherwise writes AGENTS.md and CLAUDE.md into web/ on every run.
  // The repo's root CLAUDE.md governs this project.
  agentRules: false,
  // No `X-Powered-By: Next.js`. Staging lacked it only because Vercel strips
  // it, a platform's behaviour we never verified or control; asked for here,
  // it's gone wherever the app runs (T-2.5).
  poweredByHeader: false,
  // On every response, pages and assets alike (T-2.5, D-059). Computed at
  // build time, so the CSP names the API this build calls.
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders() }];
  },
};

/**
 * Whether this run builds the site: `next build`, ours or Vercel's. `next
 * typegen` (in `pnpm typecheck`) loads this file in the build phase too, but it
 * only writes route types, so it's the one exception. If it were ever
 * misdetected, typegen would refuse loudly; a build can never skip the check.
 */
export function buildsTheSite(
  phase: string,
  argv: readonly string[] = process.argv,
): boolean {
  return phase === PHASE_PRODUCTION_BUILD && !argv.slice(2).includes("typegen");
}

/**
 * A build refuses an APP_ENV it doesn't know (T-2.6, build-env.ts): without one
 * the site builds as not-production, silently. `next dev`, `next start` and
 * `next typegen` need no APP_ENV.
 */
export default function config(phase: string): NextConfig {
  if (buildsTheSite(phase)) assertKnownAppEnv();
  return nextConfig;
}
