/**
 * The security headers on every response from the web (T-2.5, D-059).
 *
 * The CSP is enforced and exactly as strict as today's pages allow. A task
 * that needs more widens it here, deliberately, naming each host and why.
 * Until it does, its feature fails with a CSP or Permissions-Policy error,
 * and that error will look like the new feature's bug rather than this
 * policy's. The tasks that will need it, each with the same line in the plan:
 *
 *   T-3.11  Re-examined script-src 'unsafe-inline' and kept it (D-059, amended
 *           3 October 2026): the onboarding screens render only the user's own
 *           text, back to them, and the server allows only letters in a name
 *           and [a-z0-9._] in a username, so the worst is self-XSS behind
 *           React's escaping. Re-examine it when a screen first renders
 *           another user's text.
 *   T-6.6   Done: search's rows are the first screen to render another
 *           user's text (D-541). The sign-in and app routes (NONCE_ROUTES)
 *           drop 'unsafe-inline' for a nonce per request and 'strict-dynamic',
 *           set by src/proxy.ts, and render per request; every other page keeps
 *           the static policy below and stays static.
 *   T-3.14  Done: Firebase phone sign-in, on Firebase builds only (D-085).
 *           reCAPTCHA's script, frame and connect hosts, and Firebase Auth's
 *           two API hosts. Path B builds keep the policy as it was.
 *   P-68    App Check: its hosts, the way T-3.14 added Firebase's.
 *   T-4.6   Done: photos (storage-origins.ts). connect-src for the private
 *           bucket, the presigned PUT; img-src for blob: previews, the private
 *           bucket's signed links (pending and private photos) and the CDN
 *           (approved ones). Each bucket by its path, never the whole endpoint.
 *   T-4.7   Done: the selfie. camera=(self), on every page, not only
 *           /onboarding/selfie: a page reached by Next's client-side
 *           navigation keeps the policy of the document first loaded, so a
 *           policy on that one path would refuse anyone who arrived from the
 *           PIN step. The captured frame shows as a blob: image, which T-4.6's
 *           img-src already allows on every build with photo storage; a build
 *           without storage can't upload a selfie either. J2 is the standing
 *           proof (T-4.9): the fake camera opens on this page.
 *   T-4.10  Done: location, geolocation=(self). Only this site's own pages,
 *           and only after the person taps to share it (lib/geolocation.ts).
 *           J1 is the proof: the browser hands its position to the page.
 *   T-7.11  Done: voice notes. microphone=(self), on every page, as the
 *           camera is, for the same reason (a client-side navigation keeps
 *           the first document's policy); media-src for blob: (her recording's
 *           preview before she sends it) and the private bucket (a voice
 *           note's signed link, which an <audio> plays), on builds with
 *           storage. The upload is the PUT T-4.6's connect-src already allows.
 *   T-7.12  Done: real time, on the nonce routes only, where the app's
 *           socket lives (src/lib/ws.ts): connect-src for the API's own host
 *           as a socket, wss:// where the API is https:// and ws:// under
 *           local http (socketOrigin below). An http(s) source doesn't match
 *           ws(s) under CSP 3, so the API's origin alone would refuse it.
 *           Static pages keep the policy as it was; e2e/csp.spec.ts holds
 *           the browser to both.
 *   T-8.7   Done: checkout, on Razorpay builds' nonce routes only (D-761):
 *           Razorpay publishes no CSP list, so RAZORPAY below is what its
 *           Checkout asked of the page in Chrome, under this policy, read 9
 *           October 2026 (web/bench/razorpay-csp.spec.ts holds each source
 *           to a violation without it). Its frame, its logging host, its two
 *           script hosts, and inline styles, which its window's mobile layout
 *           needs. Static pages and local and CI builds keep the policy as it
 *           was. A real payment's check with test keys is P-661.
 *   T-9.12  Done: Sentry, on builds that report (staging and production,
 *           sentry-config.ts), on every page: connect-src for its ingest host,
 *           where the SDK sends errors, and the policy's own violations
 *           reported to the project's security endpoint, by `report-to` (the
 *           Reporting-Endpoints header) with `report-uri` for a browser that
 *           has only that. Until now the enforced policy was silent: a page it
 *           broke was seen only when someone complained. Local and CI builds
 *           report nothing and keep the policy as it was.
 *   T-10.2  Analytics: its script and connect hosts.
 *   P-41    Avatar's inline size style: give it classes rather than widening
 *           style-src for every page.
 *
 * HSTS is set here, not left to Vercel's default (D-074): two years, every
 * subdomain, and never preloaded. upgrade-insecure-requests is left out: never
 * measured, and by its definition it would break `next start` and the E2E over
 * local http.
 */

import { checkoutPathFor } from "./checkout-path";
import { signInPathFor } from "./sign-in-path";
import { sentryConfigFor } from "./sentry-config";
import { photoStorageFor } from "./storage-origins";

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
 * Firebase phone sign-in's sources (T-3.14, D-059), on builds that sign in by
 * Firebase only (D-081). Firebase publishes no CSP for Auth; these are
 * reCAPTCHA's own list (its FAQ, read 4 October 2026) and the two API hosts
 * the Auth SDK calls (its source, firebase 12.19.0). Not apis.google.com: that
 * is the popup and redirect sign-ins' iframe, which src/lib/firebase.ts never
 * loads. A CSP error at sign-in is this list, not a Firebase bug.
 */
const FIREBASE = {
  // reCAPTCHA's script, and the scripts it loads from gstatic.
  script: [
    "https://www.google.com/recaptcha/",
    "https://www.gstatic.com/recaptcha/",
  ],
  // reCAPTCHA's frames: the invisible widget and the challenge it may show.
  frame: [
    "https://www.google.com/recaptcha/",
    "https://recaptcha.google.com/recaptcha/",
  ],
  connect: [
    // reCAPTCHA's own requests.
    "https://www.google.com/recaptcha/",
    // Firebase Auth's API: its reCAPTCHA config, sending the code, checking it.
    "https://identitytoolkit.googleapis.com",
    // Firebase Auth's token service, should the SDK refresh its ID token.
    "https://securetoken.googleapis.com",
  ],
} as const;

/**
 * Razorpay Checkout's sources (T-8.7, D-761), on builds that pay by Razorpay
 * (checkout-path.ts), and on the nonce routes only, where the store sheet
 * lives. Razorpay publishes no CSP list; this is what its Checkout asked of
 * the page in Chrome on 9 October 2026, run under this policy by
 * web/bench/razorpay-csp.spec.ts, which also shows each one refused without
 * it. Everything inside its frame runs under Razorpay's own policy, not ours.
 * A CSP error at checkout is this list, not a Razorpay bug.
 */
const RAZORPAY = {
  // Checkout's script, and the risk-detection script it loads. 'strict-dynamic'
  // admits both in a browser that knows it; the hosts are for one that doesn't.
  script: [
    "https://checkout.razorpay.com/v1/",
    "https://cdn.razorpay.com/static/",
  ],
  // Its window. The whole host: a payment's steps (3-D Secure, UPI) move the
  // frame between its pages, unseen with a fake key (P-661).
  frame: ["https://api.razorpay.com"],
  // Its event logging, from the page (XHR and ping).
  connect: ["https://lumberjack.razorpay.com"],
} as const;

/**
 * Inline styles, which Checkout injects (a `<style>` with its mobile layout,
 * and style attributes): refused, its window loses its phone layout. Granted
 * only where its script may run (D-762, the founder's; P-661 re-checks it).
 */
const INLINE_STYLES = "style-src 'self' 'unsafe-inline'";

function paysByRazorpay(env: BuildEnv): boolean {
  return checkoutPathFor(env, { dev: isDev(env) }) === "razorpay";
}

function signsInByFirebase(env: BuildEnv): boolean {
  return signInPathFor(env, { dev: isDev(env) }) === "firebase";
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

/**
 * The API's own host as a socket (T-7.12), by `apiOrigin()`'s rule: `wss://`
 * for an `https://` API, `ws://` for local `http://`. None without an API.
 */
export function socketOrigin(env: BuildEnv = process.env): string | null {
  const api = apiOrigin(env);
  if (api === null) return null;
  const url = new URL(api);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.origin;
}

/**
 * Photos' sources (T-4.6), and voice notes' (T-7.11), on builds that have
 * storage only. A CSP error on the photos step or a voice note is this list,
 * not an upload bug.
 */
function photoSources(env: BuildEnv): {
  connect: string;
  img: string;
  media: string;
} {
  const storage = photoStorageFor(env, { dev: isDev(env) });
  if (!storage) return { connect: "", img: "", media: "" };
  return {
    // The presigned PUT, from src/lib/upload.ts, to the private bucket.
    connect: ` ${storage.privateBucket}`,
    // blob: the resized photo's preview before it uploads; the private
    // bucket: signed links to pending and private photos; the CDN: approved
    // public ones.
    img: ` blob: ${storage.privateBucket} ${storage.cdn}`,
    // Voice notes (T-7.11) live in the same private bucket: blob: her
    // recording's preview; the bucket, a voice note's signed link.
    media: ` blob: ${storage.privateBucket}`,
  };
}

/** The Reporting API's name for where violations go (`report-to`). */
export const CSP_REPORT_GROUP = "csp-endpoint";

/**
 * Sentry's sources (T-9.12), on builds that report, on every page, the static
 * ones too: an error or a violation can happen anywhere. A CSP error naming
 * sentry.io is this, not Sentry's bug.
 */
function sentrySources(env: BuildEnv): {
  connect: string;
  reporting: string[];
} {
  const sentry = sentryConfigFor(env);
  if (sentry === null) return { connect: "", reporting: [] };
  return {
    connect: ` ${sentry.ingestOrigin}`,
    reporting: [
      `report-uri ${sentry.securityEndpoint}`,
      `report-to ${CSP_REPORT_GROUP}`,
    ],
  };
}

/**
 * The routes whose pages render other people's text, or will (D-541): the
 * sign-in routes and the app's. Each is served with a nonce instead of
 * 'unsafe-inline', by src/proxy.ts, whose matcher must name exactly these
 * (a test holds it), and renders per request, since a nonce can't be baked
 * into a static page. An allowlist (CLAUDE.md rule 16): a route not named
 * keeps the static policy, and a new signed-in place is added here.
 */
export const NONCE_ROUTES = [
  "login",
  "onboarding",
  "discover",
  "chats",
  "wallet",
  "you",
  // A person's profile (T-6.5's tap, T-6.8's screen): their text.
  "people",
  // `/@username`'s page (T-6.8), behind next.config's rewrite: their text.
  "share",
  // The in-app notifications list (T-9.4).
  "notifications",
  // The moderation panel (T-9.5): reports, chats and names, other people's
  // text read by staff (D-541's trigger).
  "admin",
] as const;

/**
 * What may follow `/@` (T-6.8, D-544): a username, in any case (P-59's
 * alphabet). next.config's rewrite, the proxy's matcher and the static
 * policy's exclusion all read this one pattern, so a path that isn't a
 * username's page, a 404, keeps the static policy its page was built for.
 */
export const USERNAME_IN_PATH = "[A-Za-z0-9._]{4,20}";

/** The proxy's matcher for `/@username`: the address as the visitor asked it, before the rewrite. */
export const AT_USERNAME = `/@:username(${USERNAME_IN_PATH})`;

/** Where a build's nonce goes in `policyWithNonceSlot()`'s policy. */
export const NONCE_SLOT = "__CSP_NONCE__";

/**
 * Every path but the nonce routes and what is under them, and `/@username`, as
 * a `source` in next.config's `headers()`: the pages that get the static
 * policy.
 */
export function staticPolicySource(): string {
  return `/((?!(?:${NONCE_ROUTES.join("|")})(?:/|$)|@${USERNAME_IN_PATH}$).*)`;
}

/** A fresh nonce, 128 random bits in base64, for one response. */
export function newNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return btoa(String.fromCharCode(...bytes));
}

/**
 * The nonce routes' policy with `NONCE_SLOT` where each response's nonce
 * goes, built at build time from the same environment as the static policy,
 * so the two differ only in script-src (next.config hands it to the proxy).
 */
export function policyWithNonceSlot(env: BuildEnv = process.env): string {
  return contentSecurityPolicy(env, NONCE_SLOT);
}

/** `template`, a `policyWithNonceSlot()`, with `nonce` in its slot. */
export function policyWithNonce(template: string, nonce: string): string {
  if (!template.includes(`'nonce-${NONCE_SLOT}'`)) {
    // Never serve a page under no policy, or under one without its nonce.
    throw new Error("The build has no nonce policy: CSP_WITH_NONCE is unset");
  }
  return template.replaceAll(NONCE_SLOT, nonce);
}

export function contentSecurityPolicy(
  env: BuildEnv = process.env,
  nonce?: string,
): string {
  const dev = isDev(env);
  const api = apiOrigin(env);
  const firebase = signsInByFirebase(env);
  const photos = photoSources(env);
  const sentry = sentrySources(env);
  // Checkout lives in the store sheet, on the app's routes: the nonce routes.
  const razorpay = nonce !== undefined && paysByRazorpay(env);
  // So does the socket (T-7.12): the app's routes, signed in.
  const socket = nonce !== undefined ? socketOrigin(env) : null;
  const extra = (sources: readonly string[]) =>
    firebase ? ` ${sources.join(" ")}` : "";
  const pay = (sources: readonly string[]) =>
    razorpay ? ` ${sources.join(" ")}` : "";
  return [
    "default-src 'self'",
    // Static pages: 'unsafe-inline'. Next writes its page data as inline
    // scripts on every page; without it the waitlist form never hydrates
    // (T-2.5's trial), and they render no one's text but our own.
    // The nonce routes (D-541): this response's nonce, which Next puts on its
    // own scripts, and 'strict-dynamic', so what those load (Next's chunks,
    // Firebase's reCAPTCHA) runs and nothing injected does. 'self' and the
    // hosts stay for a browser without 'strict-dynamic', which ignores them
    // otherwise.
    `script-src 'self' ${nonce ? `'nonce-${nonce}' 'strict-dynamic'` : "'unsafe-inline'"}${dev ? " 'unsafe-eval'" : ""}${extra(FIREBASE.script)}${pay(RAZORPAY.script)}`,
    ...(dev || razorpay ? [INLINE_STYLES] : []),
    // Images fall back to default-src 'self' on a build without photos.
    ...(dev || photos.img
      ? [`img-src 'self'${dev ? " data:" : ""}${photos.img}`]
      : []),
    // Media falls back to default-src 'self' on a build without storage.
    ...(photos.media ? [`media-src 'self'${photos.media}`] : []),
    `connect-src 'self'${api ? ` ${api}` : ""}${socket ? ` ${socket}` : ""}${photos.connect}${extra(FIREBASE.connect)}${pay(RAZORPAY.connect)}${sentry.connect}`,
    // Frames fall back to default-src 'self' everywhere else; a Firebase build
    // keeps that and adds reCAPTCHA's, and a Razorpay build's nonce routes
    // Checkout's.
    ...(firebase || razorpay
      ? [`frame-src 'self'${extra(FIREBASE.frame)}${pay(RAZORPAY.frame)}`]
      : []),
    // The service worker (T-9.4): `/sw.js` from this site only, said outright
    // rather than left to script-src, whose 'strict-dynamic' ignores 'self'.
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    // A dating app is never framed: explicit, not left to a default.
    "frame-ancestors 'none'",
    // Where a violation is reported, on builds that report (T-9.12).
    ...sentry.reporting,
  ].join("; ");
}

/**
 * next.config's `headers()`: every header but the CSP on every response; the
 * static CSP on every page but the nonce routes, whose CSP is the proxy's.
 * One CSP per response, never two: a second would be enforced as well.
 */
export function headerRules(
  env: BuildEnv = process.env,
): { source: string; headers: Header[] }[] {
  const all = securityHeaders(env);
  return [
    {
      source: "/(.*)",
      headers: all.filter((h) => h.key !== "Content-Security-Policy"),
    },
    {
      source: staticPolicySource(),
      headers: all.filter((h) => h.key === "Content-Security-Policy"),
    },
  ];
}

/** Every header a static page is sent. */
export function securityHeaders(env: BuildEnv = process.env): Header[] {
  const sentry = sentryConfigFor(env);
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(env) },
    // `report-to`'s endpoint (T-9.12), on builds that report: every response,
    // the nonce routes' too, whose CSP names the same group.
    ...(sentry
      ? [
          {
            key: "Reporting-Endpoints",
            value: `${CSP_REPORT_GROUP}="${sentry.securityEndpoint}"`,
          },
        ]
      : []),
    { key: "X-Frame-Options", value: "DENY" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    {
      key: "Permissions-Policy",
      // Denied until the task that needs each allows it (see above), and
      // then to this site only, never a frame of another: the camera for the
      // selfie (T-4.7), location (T-4.10), the microphone for her voice notes
      // (T-7.11). browsing-topics opts users out of Chrome's ad-topics API.
      value:
        "camera=(self), microphone=(self), geolocation=(self), browsing-topics=()",
    },
    {
      key: "Strict-Transport-Security",
      // D-074. includeSubDomains because production's csrf cookie is scoped to
      // the whole domain (D-055): a plain-HTTP response on any subdomain could
      // overwrite it. So every subdomain must serve HTTPS, for two years after
      // a browser last saw this. Never `preload`: browsers hardcode that list,
      // removal takes months, so it is never done before launch. Browsers
      // ignore the header over plain http, so local http is unaffected.
      value: "max-age=63072000; includeSubDomains",
    },
  ];
}
