import { describe, expect, it } from "vitest";

import { configFor } from "../../next.config";

import { firebaseConfigFor } from "./firebase-config";
import { policyWithNonceSlot } from "./security-headers";
import { sentryConfigFor } from "./sentry-config";
import { SENTRY_BUILD } from "./testing/sentryEnv";

import { signInOpen, signInPath, signInPathFor } from "./sign-in-path";

describe("a build signs in by the path APP_ENV names, an allowlist (D-081)", () => {
  it.each([
    ["local", "otp"],
    ["ci", "otp"],
    ["staging", "firebase"],
    ["production", "firebase"],
  ])("%s signs in by %s", (appEnv, path) => {
    expect(signInPathFor({ APP_ENV: appEnv }, { dev: false })).toBe(path);
  });

  it("next dev with APP_ENV unset signs in by the code", () => {
    expect(signInPathFor({}, { dev: true })).toBe("otp");
  });

  it.each(["preview", "Production", "", "staging "])(
    'has no path for "%s": never a guess',
    (appEnv) => {
      expect(signInPathFor({ APP_ENV: appEnv }, { dev: true })).toBeNull();
    },
  );

  it("reads only the two values it knows from the build", () => {
    expect(signInPath("otp")).toBe("otp");
    expect(signInPath("firebase")).toBe("firebase");
    expect(signInPath("")).toBeNull();
    expect(signInPath("msg91")).toBeNull();
    expect(signInPath(undefined)).toBeNull();
  });
});

describe("whether anyone can sign in: one flag for /login and the waitlist box", () => {
  it("is open on either path since T-3.14, and closed on a build with none", () => {
    expect(signInOpen("otp")).toBe(true);
    expect(signInOpen("firebase")).toBe(true);
    expect(signInOpen(null)).toBe(false);
  });
});

// velora-ic's, as firebase-config.ts holds it (D-065, D-085).
const VELORA_IC = JSON.stringify(firebaseConfigFor({ APP_ENV: "production" }));

// Five for the browser's code, and the nonce routes' CSP for src/proxy.ts
// (D-541): public, the policy every such response sends, and inlined only
// where code reads it, which is the proxy alone.
describe("next.config builds exactly these values into the code", () => {
  it.each([
    [
      "production",
      {
        AUTH_COOKIE_SUFFIX: "prod",
        SIGN_IN_PATH: "firebase",
        CHECKOUT_PATH: "razorpay",
        FIREBASE_WEB_CONFIG: VELORA_IC,
        SENTRY_WEB_CONFIG: JSON.stringify(
          sentryConfigFor({ APP_ENV: "production", ...SENTRY_BUILD }),
        ),
      },
    ],
    [
      "staging",
      {
        AUTH_COOKIE_SUFFIX: "staging",
        SIGN_IN_PATH: "firebase",
        CHECKOUT_PATH: "razorpay",
        FIREBASE_WEB_CONFIG: VELORA_IC,
        SENTRY_WEB_CONFIG: JSON.stringify(
          sentryConfigFor({ APP_ENV: "staging", ...SENTRY_BUILD }),
        ),
      },
    ],
    [
      "local",
      {
        AUTH_COOKIE_SUFFIX: "local",
        SIGN_IN_PATH: "otp",
        CHECKOUT_PATH: "standin",
        FIREBASE_WEB_CONFIG: "",
        SENTRY_WEB_CONFIG: "",
      },
    ],
    [
      "ci",
      {
        AUTH_COOKIE_SUFFIX: "local",
        SIGN_IN_PATH: "otp",
        CHECKOUT_PATH: "standin",
        FIREBASE_WEB_CONFIG: "",
        SENTRY_WEB_CONFIG: "",
      },
    ],
  ])("APP_ENV=%s", (appEnv, env) => {
    // Every build is given Sentry's two variables: only staging and
    // production use them (T-9.12).
    const build = { APP_ENV: appEnv, ...SENTRY_BUILD };
    expect(configFor("phase-production-build", build).env).toEqual({
      ...env,
      CSP_WITH_NONCE: policyWithNonceSlot(build),
    });
  });
});
