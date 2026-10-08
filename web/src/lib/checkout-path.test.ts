import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  FAKE_KEY_ID,
  checkoutPath,
  checkoutPathFor,
  checkoutWindowFor,
} from "./checkout-path";

describe("a build takes payment by the path APP_ENV names, an allowlist (D-761)", () => {
  it.each([
    ["local", "standin"],
    ["ci", "standin"],
    ["staging", "razorpay"],
    ["production", "razorpay"],
  ])("%s pays by %s", (appEnv, path) => {
    expect(checkoutPathFor({ APP_ENV: appEnv }, { dev: false })).toBe(path);
  });

  it("next dev with APP_ENV unset pays by the stand-in", () => {
    expect(checkoutPathFor({}, { dev: true })).toBe("standin");
  });

  it("a build with APP_ENV unset, outside next dev, takes no payment", () => {
    expect(checkoutPathFor({}, { dev: false })).toBeNull();
  });

  it.each(["preview", "Production", "", "staging "])(
    'has no path for "%s": never the stand-in by default',
    (appEnv) => {
      expect(checkoutPathFor({ APP_ENV: appEnv }, { dev: true })).toBeNull();
    },
  );

  it("reads only the two values it knows from the build", () => {
    expect(checkoutPath("standin")).toBe("standin");
    expect(checkoutPath("razorpay")).toBe("razorpay");
    expect(checkoutPath("")).toBeNull();
    expect(checkoutPath("fake")).toBeNull();
    expect(checkoutPath(undefined)).toBeNull();
  });
});

describe("which window pays an order: the build's path and the order's key, both", () => {
  it("the stand-in pays the fake's orders on a stand-in build", () => {
    expect(checkoutWindowFor("standin", FAKE_KEY_ID)).toBe("standin");
  });

  it("Razorpay pays a real key's orders on a Razorpay build", () => {
    expect(checkoutWindowFor("razorpay", "rzp_live_aaaaaaaa")).toBe("razorpay");
  });

  it("a Razorpay build never opens the stand-in, even for the fake's key", () => {
    expect(checkoutWindowFor("razorpay", FAKE_KEY_ID)).toBeNull();
  });

  it("a stand-in build never takes a real key's order", () => {
    expect(checkoutWindowFor("standin", "rzp_test_aaaaaaaa")).toBeNull();
  });

  it("a build with no path opens nothing", () => {
    expect(checkoutWindowFor(null, FAKE_KEY_ID)).toBeNull();
    expect(checkoutWindowFor(null, "rzp_live_aaaaaaaa")).toBeNull();
  });
});

describe("the fake's key is the API's own", () => {
  it("is the key the fake gateway hands out (api/app/core/providers/payments.py)", () => {
    const provider = readFileSync(
      join(process.cwd(), "../api/app/core/providers/payments.py"),
      "utf8",
    );
    expect(provider).toContain(`key_id = "${FAKE_KEY_ID}"`);
    expect(FAKE_KEY_ID).toBe("rzp_fake_local_only");
  });
});
