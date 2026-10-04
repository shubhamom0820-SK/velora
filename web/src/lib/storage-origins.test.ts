// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { photoStorageFor } from "./storage-origins";

// The repo root, from web/ where vitest runs.
const ROOT = join(process.cwd(), "..");

/** `NAME = "value"` from a Fly config, or `NAME=value` from an env file. */
function setting(file: string, name: string): string {
  const text = readFileSync(join(ROOT, file), "utf8");
  const match = new RegExp(
    `^\\s*${name}\\s*=\\s*"?([^"\\n]*)"?\\s*$`,
    "m",
  ).exec(text);
  if (!match?.[1]) throw new Error(`${name} isn't set in ${file}`);
  return match[1];
}

/** What the API in `file` signs links to and serves photos from (T-4.1). */
function apiStorage(file: string) {
  const endpoint = file.endsWith(".toml")
    ? `https://${setting(file, "R2_ACCOUNT_ID")}.r2.cloudflarestorage.com`
    : setting(file, "R2_ENDPOINT_URL");
  return {
    privateBucket: `${endpoint}/${setting(file, "R2_BUCKET_PRIVATE")}/`,
    cdn: setting(file, "PUBLIC_CDN_URL"),
  };
}

describe("the web's photo storage is the API's (T-4.6)", () => {
  it.each([
    ["staging", "infra/fly.api.toml"],
    ["production", "infra/fly.api.production.toml"],
  ])("APP_ENV=%s names what %s signs and serves", (appEnv, file) => {
    expect(photoStorageFor({ APP_ENV: appEnv }, { dev: false })).toEqual(
      apiStorage(file),
    );
  });

  it.each(["local", "ci"])(
    "APP_ENV=%s names the local S3, as api/.env.example does",
    (appEnv) => {
      const local = apiStorage("api/.env.example");

      expect(photoStorageFor({ APP_ENV: appEnv }, { dev: false })).toEqual({
        privateBucket: local.privateBucket,
        // The local CDN is the public bucket's own path; a CSP source needs
        // the slash to cover what's under it.
        cdn: `${local.cdn}/`,
      });
    },
  );

  it("never lets one environment's pages reach the other's private bucket", () => {
    const staging = photoStorageFor({ APP_ENV: "staging" }, { dev: false });
    const production = photoStorageFor(
      { APP_ENV: "production" },
      { dev: false },
    );

    expect(staging?.privateBucket).toMatch(/\/velora-staging-private\/$/);
    expect(production?.privateBucket).toMatch(/\/velora-prod-private\/$/);
  });
});

describe("an allowlist (CLAUDE.md rule 16)", () => {
  it.each(["", "dev", "Staging", "preview", "[SENSITIVE]"])(
    'gives APP_ENV="%s" no storage at all',
    (appEnv) => {
      expect(photoStorageFor({ APP_ENV: appEnv }, { dev: true })).toBeNull();
    },
  );

  it("gives a build without APP_ENV none, and next dev the local S3", () => {
    expect(photoStorageFor({}, { dev: false })).toBeNull();
    expect(photoStorageFor({}, { dev: true })).toEqual(
      photoStorageFor({ APP_ENV: "local" }, { dev: false }),
    );
  });
});
