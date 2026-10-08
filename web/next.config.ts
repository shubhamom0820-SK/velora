import type { NextConfig } from "next";
import {
  PHASE_DEVELOPMENT_SERVER,
  PHASE_PRODUCTION_BUILD,
} from "next/constants";

import { authCookieSuffix } from "./src/lib/auth-cookies";
import { assertKnownAppEnv } from "./src/lib/build-env";
import { firebaseConfigFor } from "./src/lib/firebase-config";
import { signInPathFor } from "./src/lib/sign-in-path";
import { headerRules, policyWithNonceSlot } from "./src/lib/security-headers";

export const nextConfig: NextConfig = {
  // `next dev` otherwise writes AGENTS.md and CLAUDE.md into web/ on every run.
  // The repo's root CLAUDE.md governs this project.
  agentRules: false,
  // No `X-Powered-By: Next.js`. Staging lacked it only because Vercel strips
  // it, a platform's behaviour we never verified or control; asked for here,
  // it's gone wherever the app runs (T-2.5).
  poweredByHeader: false,
  // On every response, pages and assets alike (T-2.5, D-059). Computed at
  // build time, so the CSP names the API this build calls. The nonce routes'
  // CSP is src/proxy.ts's (D-541).
  async headers() {
    return headerRules();
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
 *
 * The auth cookies' suffix (T-3.10, auth-cookies.ts), the sign-in path
 * (D-081, sign-in-path.ts) and the Firebase web config (D-085,
 * firebase-config.ts) go into the browser's code here, from APP_ENV. A build
 * always has the first two, since it refused an unknown APP_ENV above, and the
 * config only where APP_ENV is staging or production; elsewhere they're empty,
 * and nothing signs in.
 */
export function configFor(
  phase: string,
  env: Readonly<Record<string, string | undefined>> = process.env,
): NextConfig {
  if (buildsTheSite(phase)) assertKnownAppEnv(env);
  const dev = phase === PHASE_DEVELOPMENT_SERVER;
  const firebase = firebaseConfigFor(env);
  return {
    ...nextConfig,
    env: {
      AUTH_COOKIE_SUFFIX: authCookieSuffix(env, { dev }) ?? "",
      // D-081: which way this build signs people in, from APP_ENV too.
      SIGN_IN_PATH: signInPathFor(env, { dev }) ?? "",
      // D-085: the Firebase project a Firebase build signs in with, as JSON;
      // empty for local and ci, which never reach Firebase.
      FIREBASE_WEB_CONFIG: firebase ? JSON.stringify(firebase) : "",
      // D-541: the nonce routes' CSP, from this build's environment as the
      // static one is, with a slot src/proxy.ts fills per response.
      CSP_WITH_NONCE: policyWithNonceSlot(env),
    },
  };
}

/**
 * What Next calls, as `config(phase, { defaultConfig })`. The second argument
 * is Next's, never the environment, so the environment is always the
 * process's here; tests pass one to `configFor`.
 */
export default function config(phase: string): NextConfig {
  return configFor(phase);
}
