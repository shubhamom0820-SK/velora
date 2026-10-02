/**
 * The security headers on every response from the web (T-2.5, D-059).
 *
 * The CSP is enforced and exactly as strict as today's pages allow. A task
 * that needs more widens it here, deliberately, naming each host and why.
 * Until it does, its feature fails with a CSP or Permissions-Policy error,
 * and that error will look like the new feature's bug rather than this
 * policy's. The tasks that will need it, each with the same line in the plan:
 *
 *   T-3.11  Re-examine script-src 'unsafe-inline': the first user-supplied text
 *           renders. Again at T-6.5, the first other people's text.
 *   T-3.14  Firebase phone sign-in: Google's script and connect hosts, and
 *           frame-src for reCAPTCHA.
 *   T-4.6   Photos: connect-src for R2's upload endpoint; img-src for the CDN
 *           and blob: previews.
 *   T-4.7   Selfie: camera=(self); blob: for the captured frame.
 *   T-4.10  Location: geolocation=(self).
 *   T-7.11  Voice notes: microphone=(self); media-src for voice notes and
 *           blob: previews.
 *   T-7.12  Real time: connect-src for wss:// on the API.
 *   T-8.7   Checkout: Razorpay's script, frame and connect hosts.
 *   T-9.12  Sentry: its connect host, and CSP reporting wired to it, so a
 *           violation in production is seen instead of silent.
 *   T-10.2  Analytics: its script and connect hosts.
 *   P-41    Avatar's inline size style: give it classes rather than widening
 *           style-src for every page.
 *
 * HSTS is Vercel's (max-age two years), not set here. includeSubDomains and
 * preload are T-2.6's decision, with their own record: preload is close to
 * irreversible. upgrade-insecure-requests is left out: never measured, and by
 * its definition it would break `next start` and the E2E over local http.
 */

/** `process.env` at build time, or a stand-in in tests. */
type BuildEnv = Readonly<Record<string, string | undefined>>;

export type Header = { key: string; value: string };

/**
 * Where the dev-only extras apply: 'unsafe-eval' and inline styles for React's
 * dev tooling and overlay, inline styles for Avatar on /dev/ui, and data:
 * images for /dev/ui's offline sample photo. `next dev` only, an allowlist
 * (CLAUDE.md rule 16): every other build is strict.
 */
const DEV_ALLOWANCES_IN: ReadonlySet<string> = new Set(["development"]);

/** Where `make dev` runs the API: the same fallback as `apiBaseUrl()` in api.ts. */
const LOCAL_API = "http://127.0.0.1:8000";

function isDev(env: BuildEnv): boolean {
  return env.NODE_ENV !== undefined && DEV_ALLOWANCES_IN.has(env.NODE_ENV);
}

/**
 * The API's origin, by the same rule as `apiBaseUrl()`: `NEXT_PUBLIC_API_URL`,
 * or the local API under `next dev`. Without either, none: such a build can't
 * call the API at all (`apiBaseUrl()` throws), so the CSP allows no API either,
 * and CI, which builds without it, still builds.
 */
export function apiOrigin(env: BuildEnv = process.env): string | null {
  const url = env.NEXT_PUBLIC_API_URL || (isDev(env) ? LOCAL_API : "");
  return url ? new URL(url).origin : null;
}

export function contentSecurityPolicy(env: BuildEnv = process.env): string {
  const dev = isDev(env);
  const api = apiOrigin(env);
  return [
    "default-src 'self'",
    // 'unsafe-inline': Next writes its page data as inline scripts on every
    // page; without it the waitlist form never hydrates (T-2.5's trial).
    // Nonces would render every page per request, spending the performance
    // margin. Justified while no user-supplied text renders: re-examined at
    // T-3.11, and at T-6.5 (D-059).
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
    ...(dev
      ? ["style-src 'self' 'unsafe-inline'", "img-src 'self' data:"]
      : []),
    `connect-src 'self'${api ? ` ${api}` : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    // A dating app is never framed: explicit, not left to a default.
    "frame-ancestors 'none'",
  ].join("; ");
}

/** Every header, for next.config's `headers()`. */
export function securityHeaders(env: BuildEnv = process.env): Header[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(env) },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    {
      key: "Permissions-Policy",
      // Denied until the task that needs each allows it (see above);
      // browsing-topics opts users out of Chrome's ad-topics API.
      value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
    },
  ];
}
