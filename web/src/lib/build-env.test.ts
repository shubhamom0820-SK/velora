import { describe, expect, it } from "vitest";

import config, {
  buildsTheSite,
  configFor,
  nextConfig,
} from "../../next.config";

import { APP_ENVS, assertKnownAppEnv } from "./build-env";

describe("a build says which environment it's for (T-2.6)", () => {
  it.each(["local", "ci", "staging", "production"])(
    "builds where APP_ENV is %s",
    (value) => {
      expect(() => assertKnownAppEnv({ APP_ENV: value })).not.toThrow();
    },
  );

  it("knows exactly the four environments", () => {
    expect(APP_ENVS).toEqual(["local", "ci", "staging", "production"]);
  });

  it("refuses an unset APP_ENV, which would build as not-production", () => {
    expect(() => assertKnownAppEnv({})).toThrow(
      "This build can't tell which environment it's for: APP_ENV is unset. " +
        "Set APP_ENV to one of local, ci, staging, production (T-2.6).",
    );
  });

  it.each(["prod", "Production", "", "staging "])(
    'refuses "%s", naming it',
    (value) => {
      expect(() => assertKnownAppEnv({ APP_ENV: value })).toThrow(
        `APP_ENV is "${value}".`,
      );
    },
  );

  it("says what fixes Vercel's Secret placeholder", () => {
    expect(() => assertKnownAppEnv({ APP_ENV: "[SENSITIVE]" })).toThrow(
      'APP_ENV is "[SENSITIVE]". Vercel stored it as a Secret, which a build ' +
        "can't read: make it Config.",
    );
  });

  it("says what a wrong one would have cost", () => {
    expect(() => assertKnownAppEnv({})).toThrow(
      "every page noindex, and its canonical and share-image URLs on http://127.0.0.1:3000",
    );
  });
});

describe("which runs build the site", () => {
  const BUILD = "phase-production-build";

  it("next build does, ours and Vercel's", () => {
    expect(buildsTheSite(BUILD, ["node", "next", "build"])).toBe(true);
  });

  it("next typegen doesn't, though Next loads the config in the build phase for it", () => {
    expect(buildsTheSite(BUILD, ["node", "next", "typegen"])).toBe(false);
  });

  it("no other phase does", () => {
    expect(
      buildsTheSite("phase-development-server", ["node", "next", "dev"]),
    ).toBe(false);
  });
});

describe("next.config runs the check for builds only", () => {
  it("refuses a production build without APP_ENV", () => {
    const saved = process.env.APP_ENV;
    delete process.env.APP_ENV;
    try {
      expect(() => config("phase-production-build")).toThrow(
        "APP_ENV is unset",
      );
    } finally {
      if (saved !== undefined) process.env.APP_ENV = saved;
    }
  });

  it.each([
    "phase-development-server",
    "phase-production-server",
    "phase-test",
  ])("leaves %s alone, so next dev and next start need no APP_ENV", (phase) => {
    // Nothing refused; only the values for the browser's code (T-3.10, D-081,
    // D-761, D-085, T-9.12) and the proxy's CSP (D-541) are added.
    const { env, ...rest } = configFor(phase, {});
    expect(rest).toEqual(nextConfig);
    expect(Object.keys(env ?? {})).toEqual([
      "AUTH_COOKIE_SUFFIX",
      "SIGN_IN_PATH",
      "CHECKOUT_PATH",
      "FIREBASE_WEB_CONFIG",
      "SENTRY_WEB_CONFIG",
      "CSP_WITH_NONCE",
    ]);
  });
});
