/**
 * Where users' photos live, for the CSP (T-4.6, D-059), chosen by `APP_ENV` at
 * build time: an allowlist (CLAUDE.md rule 16), like the sign-in path.
 *
 * - The private bucket, path-style on the S3 endpoint (T-4.1): the browser
 *   uploads to it by a presigned PUT, and shows pending and private photos from
 *   it by signed links (`GET /me/photos`).
 * - The CDN: approved public photos (`PUBLIC_CDN_URL`).
 *
 * The bucket is named by its path, so a page can reach this environment's
 * private bucket and no other on the same endpoint: staging and production
 * share one R2 account (`infra/fly.api.toml`, `infra/fly.api.production.toml`).
 * None of it is a secret: every signed link the browser is handed names it.
 * `storage-origins.test.ts` holds these to the API's own settings.
 */

/** `process.env` at build time, or a stand-in in tests. */
type BuildEnv = Readonly<Record<string, string | undefined>>;

export type PhotoStorage = {
  /** The private bucket, as a CSP source: uploads and signed links. */
  privateBucket: string;
  /** The CDN in front of the public bucket, as a CSP source. */
  cdn: string;
};

/** R2's own endpoint for the account in both Fly configs' `R2_ACCOUNT_ID`. */
const R2 = "https://82f9b26266ddb6b491a623971f87d3c7.r2.cloudflarestorage.com";

/** The local S3 (D-086) and its two buckets, as `api/.env.example` has them. */
const LOCAL: PhotoStorage = {
  privateBucket: "http://127.0.0.1:9000/velora-private/",
  cdn: "http://127.0.0.1:9000/velora-public/",
};

const STORAGE_FOR: ReadonlyMap<string, PhotoStorage> = new Map([
  ["local", LOCAL],
  // CI's API runs on the same local S3 (ci.yml starts it from the compose file).
  ["ci", LOCAL],
  [
    "staging",
    {
      privateBucket: `${R2}/velora-staging-private/`,
      cdn: "https://cdn.staging.veloraapp.co.in",
    },
  ],
  [
    "production",
    {
      privateBucket: `${R2}/velora-prod-private/`,
      cdn: "https://cdn.veloraapp.co.in",
    },
  ],
]);

/**
 * This build's photo storage, or none: every name not listed gets none, and a
 * build with none can't show or upload a photo. `next dev` without `APP_ENV`
 * uses the local S3, as `apiOrigin()` uses the local API.
 */
export function photoStorageFor(
  env: BuildEnv,
  { dev }: { dev: boolean },
): PhotoStorage | null {
  const appEnv = env.APP_ENV;
  if (appEnv === undefined) return dev ? LOCAL : null;
  return STORAGE_FOR.get(appEnv) ?? null;
}
