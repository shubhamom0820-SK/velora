import { afterEach, describe, expect, it, vi } from "vitest";

import { nextConfig } from "../../next.config";

import { apiBaseUrl } from "./api";
import {
  apiOrigin,
  contentSecurityPolicy,
  securityHeaders,
} from "./security-headers";

const STAGING = {
  NODE_ENV: "production",
  NEXT_PUBLIC_API_URL: "https://api.staging.veloraapp.co.in",
};

function header(env: Record<string, string | undefined>, key: string) {
  return securityHeaders(env).find((h) => h.key === key)?.value;
}

describe("the CSP in a production build (D-059)", () => {
  it("is exactly what today's pages need, and no more", () => {
    expect(contentSecurityPolicy(STAGING)).toBe(
      [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline'",
        "connect-src 'self' https://api.staging.veloraapp.co.in",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
      ].join("; "),
    );
  });

  it.each(["production", "test", undefined, "Development", "dev"])(
    "has none of next dev's allowances where NODE_ENV is %s",
    (nodeEnv) => {
      const csp = contentSecurityPolicy({ ...STAGING, NODE_ENV: nodeEnv });

      expect(csp).not.toContain("'unsafe-eval'");
      expect(csp).not.toContain("style-src");
      expect(csp).not.toContain("data:");
    },
  );

  it("names the API this build calls, as its origin only", () => {
    const csp = contentSecurityPolicy({
      NODE_ENV: "production",
      NEXT_PUBLIC_API_URL: "https://api.example.test/some/path/",
    });

    expect(csp).toContain("connect-src 'self' https://api.example.test;");
  });

  it("names no API when the build has none, as CI's doesn't", () => {
    expect(contentSecurityPolicy({ NODE_ENV: "production" })).toContain(
      "connect-src 'self';",
    );
  });

  it("leaves out upgrade-insecure-requests: unmeasured, and it would break local http", () => {
    expect(contentSecurityPolicy(STAGING)).not.toContain(
      "upgrade-insecure-requests",
    );
  });
});

describe("under next dev only", () => {
  const DEV = { NODE_ENV: "development" };

  it("adds what React's dev tooling needs, and the local API", () => {
    const csp = contentSecurityPolicy(DEV);

    expect(csp).toContain("script-src 'self' 'unsafe-inline' 'unsafe-eval'");
    expect(csp).toContain("style-src 'self' 'unsafe-inline'");
    // /dev/ui's offline sample photo.
    expect(csp).toContain("img-src 'self' data:");
    expect(csp).toContain("connect-src 'self' http://127.0.0.1:8000;");
  });
});

describe("framing: a dating app is never framed", () => {
  it("forbids it twice, explicitly", () => {
    expect(contentSecurityPolicy(STAGING)).toContain("frame-ancestors 'none'");
    expect(header(STAGING, "X-Frame-Options")).toBe("DENY");
  });
});

describe("the other headers", () => {
  it("are exactly these", () => {
    expect(securityHeaders(STAGING).map((h) => h.key)).toEqual([
      "Content-Security-Policy",
      "X-Frame-Options",
      "X-Content-Type-Options",
      "Referrer-Policy",
      "Permissions-Policy",
      "Strict-Transport-Security",
    ]);
    expect(header(STAGING, "X-Content-Type-Options")).toBe("nosniff");
    expect(header(STAGING, "Referrer-Policy")).toBe(
      "strict-origin-when-cross-origin",
    );
  });

  it("deny camera, microphone and location until the task that needs each allows it", () => {
    expect(header(STAGING, "Permissions-Policy")).toBe(
      "camera=(), microphone=(), geolocation=(), browsing-topics=()",
    );
  });

  it("set HSTS as D-074 decided: two years, every subdomain", () => {
    expect(header(STAGING, "Strict-Transport-Security")).toBe(
      "max-age=63072000; includeSubDomains",
    );
  });

  it("never preload HSTS: effectively irreversible, so never before launch (D-074)", () => {
    expect(JSON.stringify(securityHeaders(STAGING))).not.toMatch(/preload/i);
  });
});

describe("the CSP and api.ts agree on the API", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("names the origin apiBaseUrl() calls", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test/");

    expect(apiOrigin()).toBe(new URL(apiBaseUrl()).origin);
  });

  it("names none where apiBaseUrl() refuses to call one", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");
    vi.stubEnv("NODE_ENV", "production");

    expect(() => apiBaseUrl()).toThrow();
    expect(apiOrigin()).toBeNull();
  });
});

describe("next.config", () => {
  it("asks for no X-Powered-By, rather than trusting the platform to strip it", () => {
    expect(nextConfig.poweredByHeader).toBe(false);
  });

  it("sends the headers on every response", async () => {
    const rules = await nextConfig.headers?.();

    expect(rules).toEqual([{ source: "/(.*)", headers: securityHeaders() }]);
  });
});
