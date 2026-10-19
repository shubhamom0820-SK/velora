import { describe, expect, it } from "vitest";

import { configFor } from "../../next.config";

import {
  SENTRY_IN,
  assertSentryConfigured,
  sentryConfig,
  sentryConfigFor,
} from "./sentry-config";
import { SENTRY_BUILD } from "./testing/sentryEnv";

// The shared test DSN's own parts, never a second copy of them.
const DSN = new URL(SENTRY_BUILD.NEXT_PUBLIC_SENTRY_DSN);
const KEY = DSN.username;
const HOST = DSN.host;
const PROJECT = DSN.pathname.slice(1);
const SHA = SENTRY_BUILD.NEXT_PUBLIC_SENTRY_RELEASE;

describe("which builds report to Sentry (T-9.12), an allowlist", () => {
  it("is staging and production only", () => {
    expect([...SENTRY_IN].sort()).toEqual(["production", "staging"]);
  });

  it.each(["local", "ci", "preview", "", undefined])(
    "APP_ENV=%s reports nothing, whatever the variables say",
    (appEnv) => {
      expect(sentryConfigFor({ APP_ENV: appEnv, ...SENTRY_BUILD })).toBeNull();
      expect(() => assertSentryConfigured({ APP_ENV: appEnv })).not.toThrow();
    },
  );

  it.each(["staging", "production"])(
    "APP_ENV=%s reports, its endpoints worked out from the DSN",
    (appEnv) => {
      expect(sentryConfigFor({ APP_ENV: appEnv, ...SENTRY_BUILD })).toEqual({
        dsn: SENTRY_BUILD.NEXT_PUBLIC_SENTRY_DSN,
        release: SHA,
        environment: appEnv,
        ingestOrigin: `https://${HOST}`,
        securityEndpoint:
          `https://${HOST}/api/${PROJECT}/security/` +
          `?sentry_key=${KEY}&sentry_environment=${appEnv}&sentry_release=${SHA}`,
      });
    },
  );
});

describe("a build that reports refuses to finish without both (D-1001)", () => {
  it.each([
    [
      {},
      "NEXT_PUBLIC_SENTRY_DSN is unset; and NEXT_PUBLIC_SENTRY_RELEASE is unset",
    ],
    [
      { NEXT_PUBLIC_SENTRY_DSN: SENTRY_BUILD.NEXT_PUBLIC_SENTRY_DSN },
      "NEXT_PUBLIC_SENTRY_RELEASE is unset",
    ],
    [{ NEXT_PUBLIC_SENTRY_RELEASE: SHA }, "NEXT_PUBLIC_SENTRY_DSN is unset"],
  ])("%j: %s", (variables, problem) => {
    for (const appEnv of ["staging", "production"]) {
      expect(() =>
        assertSentryConfigured({ APP_ENV: appEnv, ...variables }),
      ).toThrow(
        `A ${appEnv} build reports its errors to Sentry, and ${problem}`,
      );
      expect(sentryConfigFor({ APP_ENV: appEnv, ...variables })).toBeNull();
    }
  });

  it.each([
    `http://${KEY}@${HOST}/${PROJECT}`,
    `https://${KEY}@sentry.example.com/${PROJECT}`,
    `https://${KEY}@${HOST}/`,
    `"https://${KEY}@${HOST}/${PROJECT}"`,
  ])("refuses the DSN %s without echoing it", (dsn) => {
    const build = {
      APP_ENV: "staging",
      NEXT_PUBLIC_SENTRY_DSN: dsn,
      NEXT_PUBLIC_SENTRY_RELEASE: SHA,
    };
    expect(() => assertSentryConfigured(build)).toThrow(
      "NEXT_PUBLIC_SENTRY_DSN isn't a Sentry DSN",
    );
    expect(() => assertSentryConfigured(build)).not.toThrow(KEY);
    expect(sentryConfigFor(build)).toBeNull();
  });

  it.each(["abc123", SHA.toUpperCase(), `${SHA}0`])(
    "refuses the release %s",
    (release) => {
      expect(() =>
        assertSentryConfigured({
          APP_ENV: "production",
          NEXT_PUBLIC_SENTRY_DSN: SENTRY_BUILD.NEXT_PUBLIC_SENTRY_DSN,
          NEXT_PUBLIC_SENTRY_RELEASE: release,
        }),
      ).toThrow("NEXT_PUBLIC_SENTRY_RELEASE isn't a commit's full SHA");
    },
  );

  it("next.config refuses such a build, and leaves next dev and start alone", () => {
    expect(() =>
      configFor("phase-production-build", { APP_ENV: "staging" }),
    ).toThrow("A staging build reports its errors to Sentry");
    for (const phase of [
      "phase-development-server",
      "phase-production-server",
    ]) {
      expect(
        configFor(phase, { APP_ENV: "staging" }).env?.SENTRY_WEB_CONFIG,
      ).toBe("");
    }
  });

  it("next.config puts the config into the build, or nothing", () => {
    const staging = configFor("phase-production-build", {
      APP_ENV: "staging",
      ...SENTRY_BUILD,
    }).env?.SENTRY_WEB_CONFIG;
    expect(sentryConfig(staging)).toEqual(
      sentryConfigFor({ APP_ENV: "staging", ...SENTRY_BUILD }),
    );
    expect(
      configFor("phase-production-build", { APP_ENV: "ci", ...SENTRY_BUILD })
        .env?.SENTRY_WEB_CONFIG,
    ).toBe("");
  });
});

describe("the config read back from the bundle", () => {
  it.each([undefined, "", "not json", "{}", '{"dsn":"x"}', "null"])(
    "%s is none, never a guess",
    (value) => {
      expect(sentryConfig(value)).toBeNull();
    },
  );
});
