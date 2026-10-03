/**
 * Which way a build signs people in (D-081), fixed at build time from
 * `APP_ENV`: `next.config` puts it in `SIGN_IN_PATH`. An allowlist (CLAUDE.md
 * rule 16), like the auth cookies' suffix; the web never reads
 * `AUTH_PHONE_PROVIDER`.
 *
 * - `otp`: Path B, `/v1/auth/otp/*` (the fake provider locally, MSG91 later).
 * - `firebase`: Path A (T-3.14): Firebase texts the code from the browser and
 *   `/v1/auth/firebase` exchanges its token (D-085). Staging and production,
 *   where Path B answers 404 (D-066).
 */
export type SignInPath = "otp" | "firebase";

type BuildEnv = Readonly<Record<string, string | undefined>>;

const PATH_FOR: ReadonlyMap<string, SignInPath> = new Map([
  ["local", "otp"],
  ["ci", "otp"],
  ["staging", "firebase"],
  ["production", "firebase"],
]);

export function signInPathFor(
  env: BuildEnv,
  { dev }: { dev: boolean },
): SignInPath | null {
  const appEnv = env.APP_ENV;
  if (appEnv === undefined) return dev ? "otp" : null;
  return PATH_FOR.get(appEnv) ?? null;
}

/**
 * Whether anyone can sign in on this build: either path, since T-3.14. A build
 * with neither still says sign-in isn't open. /login's closed screen and the
 * landing page's waitlist heading both read it, so they can't disagree (D-081).
 */
export function signInOpen(path: SignInPath | null = signInPath()): boolean {
  return path !== null;
}

/**
 * This build's path. A build with none has no way to sign in, and is shown
 * the closed screen: never a guess.
 */
export function signInPath(
  value: string | undefined = process.env.SIGN_IN_PATH,
): SignInPath | null {
  return value === "otp" || value === "firebase" ? value : null;
}
