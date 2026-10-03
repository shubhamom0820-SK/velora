/**
 * The auth cookies' names, which carry the environment (D-055): `csrf_prod`,
 * `csrf_staging`, `csrf_local`, and the refresh cookie's twins, which only the
 * API reads. The web reads one cookie, this environment's CSRF value, to send
 * back as `X-CSRF` (D-024).
 *
 * The suffix is fixed at build time from `APP_ENV`: `next.config` puts it in
 * `AUTH_COOKIE_SUFFIX` (T-3.10). No Vercel variable of its own: a build already
 * says which environment it's for (T-2.6).
 */

/** `process.env`, or a stand-in in tests. */
type BuildEnv = Readonly<Record<string, string | undefined>>;

/**
 * Which suffix each environment's build expects: an allowlist (CLAUDE.md rule
 * 16). `ci` builds run T-3.13's E2E against an API whose `ENV` is `local`, so
 * they read `_local`. Anything else has no suffix, and so no session: a build
 * refuses an unknown `APP_ENV` anyway (build-env.ts).
 */
const SUFFIX_FOR: ReadonlyMap<string, string> = new Map([
  ["production", "prod"],
  ["staging", "staging"],
  ["local", "local"],
  ["ci", "local"],
]);

/**
 * The suffix for this build, or null where there is none. Under `next dev`
 * with `APP_ENV` unset, `local`: `make dev` sets nothing.
 */
export function authCookieSuffix(
  env: BuildEnv,
  { dev }: { dev: boolean },
): string | null {
  const appEnv = env.APP_ENV;
  if (appEnv === undefined) return dev ? "local" : null;
  return SUFFIX_FOR.get(appEnv) ?? null;
}

/**
 * This environment's CSRF cookie name. Throws in a build with no suffix rather
 * than guess one: guessing is how one environment would read another's cookie.
 */
export function csrfCookieName(
  suffix: string | undefined = process.env.AUTH_COOKIE_SUFFIX,
): string {
  if (!suffix) {
    throw new Error(
      "This build has no AUTH_COOKIE_SUFFIX, so it can't name its auth cookies (T-3.10).",
    );
  }
  return `csrf_${suffix}`;
}

/**
 * The value of the cookie called exactly `name`, or null. `csrf` and
 * `csrf_localx` are other cookies: only the whole name matches.
 */
export function readCookie(
  name: string,
  cookies: string = typeof document === "undefined" ? "" : document.cookie,
): string | null {
  for (const pair of cookies.split(";")) {
    const separator = pair.indexOf("=");
    if (separator === -1) continue;
    if (pair.slice(0, separator).trim() === name) {
      return decodeURIComponent(pair.slice(separator + 1).trim());
    }
  }
  return null;
}
