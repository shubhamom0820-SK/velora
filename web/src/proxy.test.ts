import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { proxy } from "./proxy";
import { policyWithNonceSlot } from "./lib/security-headers";

const STAGING = {
  NODE_ENV: "production",
  APP_ENV: "staging",
  NEXT_PUBLIC_API_URL: "https://api.staging.veloraapp.co.in",
};

function nonceOf(policy: string | null): string | undefined {
  return policy?.match(/'nonce-([^']+)'/)?.[1];
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("the proxy (T-6.6, D-541)", () => {
  it("sends the build's policy with a fresh nonce, on the response and to Next's render", () => {
    vi.stubEnv("CSP_WITH_NONCE", policyWithNonceSlot(STAGING));

    const first = proxy(new NextRequest("https://veloraapp.co.in/discover"));
    const second = proxy(new NextRequest("https://veloraapp.co.in/discover"));

    const policy = first.headers.get("Content-Security-Policy");
    expect(policy).toContain("'strict-dynamic'");
    // Never for scripts. Styles may be, on a Razorpay build (D-762).
    expect(policy?.match(/script-src [^;]*/)?.[0]).not.toContain(
      "'unsafe-inline'",
    );
    const nonce = nonceOf(policy);
    expect(nonce).toBeDefined();
    expect(nonceOf(second.headers.get("Content-Security-Policy"))).not.toBe(
      nonce,
    );
    // NextResponse.next({ request: { headers } }) hands Next the request's
    // headers this way; Next reads the nonce from this one.
    expect(
      first.headers.get("x-middleware-request-content-security-policy"),
    ).toBe(policy);
  });

  it("refuses to serve a page when the build has no nonce policy", () => {
    vi.stubEnv("CSP_WITH_NONCE", "");

    expect(() =>
      proxy(new NextRequest("https://veloraapp.co.in/discover")),
    ).toThrow(/CSP_WITH_NONCE/);
  });
});

describe("the nonce routes render per request (D-541)", () => {
  it("has (auth) and (app) force dynamic rendering, so no page is built ahead without its nonce", async () => {
    const auth = await import("./app/(auth)/layout");
    const app = await import("./app/(app)/layout");

    expect(auth.dynamic).toBe("force-dynamic");
    expect(app.dynamic).toBe("force-dynamic");
  });
});
