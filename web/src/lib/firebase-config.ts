/**
 * The Firebase web config each build signs in with (T-3.14, D-085), chosen by
 * `APP_ENV` at build time: `next.config` puts it in `FIREBASE_WEB_CONFIG`. An
 * allowlist (CLAUDE.md rule 16), like the sign-in path it goes with (D-081).
 *
 * Only staging and production have one, and both are `velora-ic`, the project
 * they share (D-065) until P-66 gives staging a project of its own and its line
 * here changes. Local and ci builds have none, so nothing built on a dev
 * machine can reach Firebase, and no seeded number (D-064) can be texted from
 * one: they sign in by Path B instead.
 *
 * None of it is a secret. Firebase's own page on API keys (read 4 October
 * 2026): they "are not used to control access to backend resources", and they
 * "are OK to include in code or checked-in config files". The key names the
 * project to Google and grants nothing by itself; every Firebase site ships it
 * in its bundle. What stops abuse is elsewhere: the authorised domains, the
 * SMS region policy, App Check from P-68, and our API's checks on the token it
 * is handed (D-085). gitleaks flags any Google API key, so the key's line
 * carries its allow marker, for that reason.
 */

/** What `initializeApp` needs for phone sign-in, and nothing more. */
export type FirebaseWebConfig = {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
};

type BuildEnv = Readonly<Record<string, string | undefined>>;

const VELORA_IC: FirebaseWebConfig = {
  apiKey: "AIzaSyBQW56SeM4wkIGKONyLh9FiUv4yGDFVdp0", // gitleaks:allow (public by design: see above)
  authDomain: "velora-ic.firebaseapp.com",
  projectId: "velora-ic",
  appId: "1:432265944495:web:61ce04d5f2581e31b5e35a",
};

const CONFIG_FOR: ReadonlyMap<string, FirebaseWebConfig> = new Map([
  ["staging", VELORA_IC],
  ["production", VELORA_IC],
]);

/** This `APP_ENV`'s config, or none: every name not listed gets none. */
export function firebaseConfigFor(env: BuildEnv): FirebaseWebConfig | null {
  const appEnv = env.APP_ENV;
  return appEnv === undefined ? null : (CONFIG_FOR.get(appEnv) ?? null);
}

/**
 * This build's config, read back from what `next.config` put in the bundle.
 * Anything that isn't a whole config is none: never a guess.
 */
export function firebaseConfig(
  value: string | undefined = process.env.FIREBASE_WEB_CONFIG,
): FirebaseWebConfig | null {
  if (!value) return null;
  try {
    const parsed: unknown = JSON.parse(value);
    return isConfig(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function isConfig(value: unknown): value is FirebaseWebConfig {
  if (typeof value !== "object" || value === null) return false;
  const fields = value as Record<string, unknown>;
  return (["apiKey", "authDomain", "projectId", "appId"] as const).every(
    (name) => typeof fields[name] === "string" && fields[name] !== "",
  );
}
