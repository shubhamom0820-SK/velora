import { describe, expect, it, vi } from "vitest";

import config, { configFor } from "../../next.config";
import { SENTRY_BUILD } from "./testing/sentryEnv";

import { authCookieSuffix, csrfCookieName, readCookie } from "./auth-cookies";

describe("the auth cookies' suffix follows APP_ENV, an allowlist (T-3.10, D-055)", () => {
  it.each([
    ["production", "prod"],
    ["staging", "staging"],
    ["local", "local"],
    ["ci", "local"],
  ])("a build for %s reads _%s", (appEnv, suffix) => {
    expect(authCookieSuffix({ APP_ENV: appEnv }, { dev: false })).toBe(suffix);
  });

  it("next dev with APP_ENV unset reads _local", () => {
    expect(authCookieSuffix({}, { dev: true })).toBe("local");
  });

  it.each(["preview", "prod", "Production", "", "staging "])(
    'has no suffix for "%s": never a fallback to another environment\'s',
    (appEnv) => {
      expect(authCookieSuffix({ APP_ENV: appEnv }, { dev: true })).toBeNull();
    },
  );

  it("has none outside next dev with APP_ENV unset", () => {
    expect(authCookieSuffix({}, { dev: false })).toBeNull();
  });
});

describe("next.config puts the suffix into the build", () => {
  it.each([
    ["production", "prod"],
    ["staging", "staging"],
    ["local", "local"],
    ["ci", "local"],
  ])("APP_ENV=%s builds with AUTH_COOKIE_SUFFIX=%s", (appEnv, suffix) => {
    expect(
      configFor("phase-production-build", { APP_ENV: appEnv, ...SENTRY_BUILD })
        .env?.AUTH_COOKIE_SUFFIX,
    ).toBe(suffix);
  });

  it("next dev with APP_ENV unset gets local", () => {
    expect(
      configFor("phase-development-server", {}).env?.AUTH_COOKIE_SUFFIX,
    ).toBe("local");
  });

  it("reads the process's APP_ENV when Next calls it with its own second argument", () => {
    vi.stubEnv("APP_ENV", "staging");
    for (const [name, value] of Object.entries(SENTRY_BUILD)) {
      vi.stubEnv(name, value);
    }
    try {
      // How Next calls it (next.config's own docs): (phase, { defaultConfig }).
      const call = config as unknown as (
        phase: string,
        context: { defaultConfig: object },
      ) => ReturnType<typeof config>;
      expect(call("phase-production-build", { defaultConfig: {} }).env).toEqual(
        expect.objectContaining({
          AUTH_COOKIE_SUFFIX: "staging",
          SIGN_IN_PATH: "firebase",
        }),
      );
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it("a build with an unknown APP_ENV is refused before it gets a suffix", () => {
    expect(() =>
      configFor("phase-production-build", { APP_ENV: "preview" }),
    ).toThrow('APP_ENV is "preview"');
  });
});

describe("the CSRF cookie", () => {
  it("is csrf_ and the suffix", () => {
    expect(csrfCookieName("staging")).toBe("csrf_staging");
  });

  it("can't be named without a suffix", () => {
    expect(() => csrfCookieName("")).toThrow(
      "This build has no AUTH_COOKIE_SUFFIX, so it can't name its auth cookies (T-3.10).",
    );
    expect(() => csrfCookieName(undefined)).toThrow("AUTH_COOKIE_SUFFIX");
  });

  it("is read by its whole name, never a bare csrf or another environment's", () => {
    const jar =
      "csrf=bare; csrf_prod=production; csrf_localx=other; csrf_local=ours; theme=dark";

    expect(readCookie("csrf_local", jar)).toBe("ours");
    expect(readCookie("csrf_staging", jar)).toBeNull();
  });

  it("keeps an = inside the value and decodes it", () => {
    expect(readCookie("csrf_local", "csrf_local=a%3Db=c")).toBe("a=b=c");
  });
});
