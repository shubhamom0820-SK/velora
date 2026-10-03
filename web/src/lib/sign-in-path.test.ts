import { describe, expect, it } from "vitest";

import { configFor } from "../../next.config";

import { firebaseConfigFor } from "./firebase-config";

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

describe("next.config builds exactly these three values into the browser's code", () => {
  it.each([
    [
      "production",
      {
        AUTH_COOKIE_SUFFIX: "prod",
        SIGN_IN_PATH: "firebase",
        FIREBASE_WEB_CONFIG: VELORA_IC,
      },
    ],
    [
      "staging",
      {
        AUTH_COOKIE_SUFFIX: "staging",
        SIGN_IN_PATH: "firebase",
        FIREBASE_WEB_CONFIG: VELORA_IC,
      },
    ],
    [
      "local",
      {
        AUTH_COOKIE_SUFFIX: "local",
        SIGN_IN_PATH: "otp",
        FIREBASE_WEB_CONFIG: "",
      },
    ],
    [
      "ci",
      {
        AUTH_COOKIE_SUFFIX: "local",
        SIGN_IN_PATH: "otp",
        FIREBASE_WEB_CONFIG: "",
      },
    ],
  ])("APP_ENV=%s", (appEnv, env) => {
    expect(
      configFor("phase-production-build", { APP_ENV: appEnv }).env,
    ).toEqual(env);
  });
});
