/**
 * Which environment a build is for (T-2.6). `next build` refuses unless
 * `APP_ENV` names one of these: an allowlist (CLAUDE.md rule 16).
 *
 * Why it exists: `APP_ENV` decides the site's address and whether search
 * engines may index it (site.ts). A build without it, or with a value we don't
 * know, quietly builds as "not production": every page `noindex`, an empty
 * sitemap, and the canonical URL and share image on http://127.0.0.1:3000.
 * Until P-0.3, D-053's legal-facts gate caught that by accident, because a fact
 * was missing; with every fact known it no longer can. Proved on 3 October
 * 2026: a build with `APP_ENV` unset passed and served exactly that.
 *
 * An allowlist only catches a value that isn't one of these. A valid but wrong
 * one, `staging` on the production project, passes here, so the smoke check
 * also compares the home page's canonical address with the site it checks.
 */

/** The environments a build may be for. */
export const APP_ENVS: readonly string[] = [
  "local",
  "ci",
  "staging",
  "production",
];

/** `process.env` at build time, or a stand-in in tests. */
type BuildEnv = Readonly<Record<string, string | undefined>>;

export function assertKnownAppEnv(env: BuildEnv = process.env): void {
  const value = env.APP_ENV;
  if (value !== undefined && APP_ENVS.includes(value)) return;
  const got =
    value === undefined ? "APP_ENV is unset" : `APP_ENV is "${value}"`;
  // Vercel writes a Secret back as this placeholder when the build pulls it
  // (infra/STAGING.md), so say what fixes it.
  const hint =
    value === "[SENSITIVE]"
      ? " Vercel stored it as a Secret, which a build can't read: make it Config."
      : "";
  throw new Error(
    `This build can't tell which environment it's for: ${got}.${hint} ` +
      `Set APP_ENV to one of ${APP_ENVS.join(", ")} (T-2.6). Without it, ` +
      "the site would build as not-production: every page noindex, and its " +
      "canonical and share-image URLs on http://127.0.0.1:3000.",
  );
}
