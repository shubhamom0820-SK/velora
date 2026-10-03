import { describe, expect, it } from "vitest";

import { firebaseConfig, firebaseConfigFor } from "./firebase-config";

describe("which Firebase project a build signs in with, by APP_ENV (D-085)", () => {
  it.each(["staging", "production"])(
    "%s signs in with velora-ic, the one project both share (D-065)",
    (appEnv) => {
      expect(firebaseConfigFor({ APP_ENV: appEnv })).toEqual({
        apiKey: expect.stringMatching(/^AIza[0-9A-Za-z_-]{35}$/),
        authDomain: "velora-ic.firebaseapp.com",
        projectId: "velora-ic",
        appId: expect.stringMatching(/^1:432265944495:web:[0-9a-f]+$/),
      });
    },
  );

  it.each(["local", "ci"])(
    "%s has none, so nothing built on a dev machine reaches Firebase (D-064)",
    (appEnv) => {
      expect(firebaseConfigFor({ APP_ENV: appEnv })).toBeNull();
    },
  );

  it.each([
    "preview",
    "Production",
    "",
    "staging ",
    "env-nobody-has-named-2031",
  ])('has none for "%s": an allowlist, never a guess', (appEnv) => {
    expect(firebaseConfigFor({ APP_ENV: appEnv })).toBeNull();
  });

  it("has none with APP_ENV unset, as under next dev", () => {
    expect(firebaseConfigFor({})).toBeNull();
  });
});

describe("the config read back from the bundle", () => {
  const whole = firebaseConfigFor({ APP_ENV: "staging" });

  it("is the one next.config put there", () => {
    expect(firebaseConfig(JSON.stringify(whole))).toEqual(whole);
  });

  it.each([
    ["empty", ""],
    ["missing", undefined],
    ["not JSON", "{apiKey:"],
    ["a string", '"velora-ic"'],
    ["missing its app ID", JSON.stringify({ ...whole, appId: undefined })],
    ["with an empty key", JSON.stringify({ ...whole, apiKey: "" })],
  ])("is none when %s", (_, value) => {
    expect(firebaseConfig(value)).toBeNull();
  });
});
