import { afterEach, describe, expect, it, vi } from "vitest";

import { nextConfig } from "../../next.config";

import { apiBaseUrl } from "./api";
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";

import { config as proxyConfig } from "../proxy";

import {
  apiOrigin,
  contentSecurityPolicy,
  headerRules,
  AT_USERNAME,
  NONCE_ROUTES,
  NONCE_SLOT,
  newNonce,
  policyWithNonce,
  policyWithNonceSlot,
  securityHeaders,
  socketOrigin,
  staticPolicySource,
} from "./security-headers";
import { socketUrl } from "./ws";

const STAGING = {
  NODE_ENV: "production",
  NEXT_PUBLIC_API_URL: "https://api.staging.veloraapp.co.in",
};

function header(env: Record<string, string | undefined>, key: string) {
  return securityHeaders(env).find((h) => h.key === key)?.value;
}

/** Each environment's photo storage (T-4.6, storage-origins.ts). */
const R2 = "https://82f9b26266ddb6b491a623971f87d3c7.r2.cloudflarestorage.com";
const LOCAL_S3 = {
  img: "img-src 'self' blob: http://127.0.0.1:9000/velora-private/ http://127.0.0.1:9000/velora-public/",
  // Voice notes (T-7.11): her recording's preview, and their signed links.
  media: "media-src 'self' blob: http://127.0.0.1:9000/velora-private/",
  upload: "http://127.0.0.1:9000/velora-private/",
};
const R2_FOR = {
  staging: {
    img: `img-src 'self' blob: ${R2}/velora-staging-private/ https://cdn.staging.veloraapp.co.in`,
    media: `media-src 'self' blob: ${R2}/velora-staging-private/`,
    upload: `${R2}/velora-staging-private/`,
  },
  production: {
    img: `img-src 'self' blob: ${R2}/velora-prod-private/ https://cdn.veloraapp.co.in`,
    media: `media-src 'self' blob: ${R2}/velora-prod-private/`,
    upload: `${R2}/velora-prod-private/`,
  },
} as const;

describe("the CSP in a production build (D-059)", () => {
  it("is exactly what a build without photo storage needs, and no more", () => {
    expect(contentSecurityPolicy(STAGING)).toBe(
      [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline'",
        "connect-src 'self' https://api.staging.veloraapp.co.in",
        "worker-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
      ].join("; "),
    );
  });

  it.each(["local", "ci"])(
    "adds exactly the local S3's photo sources on a Path B build, APP_ENV=%s: no Google host at all (T-4.6)",
    (appEnv) => {
      const csp = contentSecurityPolicy({ ...STAGING, APP_ENV: appEnv });

      expect(csp).toBe(
        [
          "default-src 'self'",
          "script-src 'self' 'unsafe-inline'",
          LOCAL_S3.img,
          LOCAL_S3.media,
          `connect-src 'self' https://api.staging.veloraapp.co.in ${LOCAL_S3.upload}`,
          "worker-src 'self'",
          "object-src 'none'",
          "base-uri 'none'",
          "form-action 'self'",
          "frame-ancestors 'none'",
        ].join("; "),
      );
      expect(csp).not.toContain("google");
      expect(csp).not.toContain("frame-src");
    },
  );

  it.each(["staging", "production"] as const)(
    "adds exactly Firebase sign-in's hosts (T-3.14) and this environment's photo storage (T-4.6) on a Firebase build, APP_ENV=%s",
    (appEnv) => {
      expect(contentSecurityPolicy({ ...STAGING, APP_ENV: appEnv })).toBe(
        [
          "default-src 'self'",
          "script-src 'self' 'unsafe-inline' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/",
          R2_FOR[appEnv].img,
          R2_FOR[appEnv].media,
          `connect-src 'self' https://api.staging.veloraapp.co.in ${R2_FOR[appEnv].upload} https://www.google.com/recaptcha/ https://identitytoolkit.googleapis.com https://securetoken.googleapis.com`,
          "frame-src 'self' https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/",
          "worker-src 'self'",
          "object-src 'none'",
          "base-uri 'none'",
          "form-action 'self'",
          "frame-ancestors 'none'",
        ].join("; "),
      );
    },
  );

  it.each(["local", "ci", "staging", "production"])(
    "names each bucket by its path, never a whole storage endpoint or a wildcard, APP_ENV=%s",
    (appEnv) => {
      const csp = contentSecurityPolicy({ ...STAGING, APP_ENV: appEnv });

      expect(csp).not.toContain("*");
      expect(csp).not.toMatch(/r2\.cloudflarestorage\.com[ ;]/);
      expect(csp).not.toMatch(/127\.0\.0\.1:9000[ ;]/);
      // Uploads only ever go to the private bucket, and voice notes only
      // ever play from it.
      expect(csp).not.toMatch(/connect-src[^;]*-public/);
      expect(csp).not.toMatch(/media-src[^;]*-public/);
    },
  );

  it("never adds apis.google.com, the popup sign-ins' iframe we never load", () => {
    const csp = contentSecurityPolicy({ ...STAGING, APP_ENV: "production" });

    expect(csp).not.toContain("apis.google.com");
    expect(csp).not.toContain("firebaseapp.com");
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
    // /dev/ui's offline sample photo, and the local S3's photos (T-4.6).
    expect(csp).toContain(
      "img-src 'self' data: blob: http://127.0.0.1:9000/velora-private/ http://127.0.0.1:9000/velora-public/;",
    );
    expect(csp).toContain(
      "media-src 'self' blob: http://127.0.0.1:9000/velora-private/;",
    );
    expect(csp).toContain(
      "connect-src 'self' http://127.0.0.1:8000 http://127.0.0.1:9000/velora-private/;",
    );
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

  it("allow the camera (T-4.7), location (T-4.10) and the microphone (T-7.11) to this site alone, never a frame of another", () => {
    for (const env of [
      STAGING,
      { ...STAGING, APP_ENV: "staging" },
      { ...STAGING, APP_ENV: "production" },
      { NODE_ENV: "development" },
    ])
      expect(header(env, "Permissions-Policy")).toBe(
        "camera=(self), microphone=(self), geolocation=(self), browsing-topics=()",
      );
  });

  it("keep blob: images wherever a selfie can be taken, for its captured frame (T-4.7)", () => {
    // A selfie needs photo storage to go up, and every build with storage
    // allows blob: images (T-4.6), so the frame shows wherever it's taken.
    for (const env of [
      { ...STAGING, APP_ENV: "local" },
      { ...STAGING, APP_ENV: "ci" },
      { ...STAGING, APP_ENV: "staging" },
      { ...STAGING, APP_ENV: "production" },
    ])
      expect(contentSecurityPolicy(env)).toMatch(/img-src 'self' blob: /);
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

  it("sends every header on every response, and the static CSP everywhere but the nonce routes", async () => {
    const rules = await nextConfig.headers?.();

    expect(rules).toEqual(headerRules());
    const all = securityHeaders();
    expect(rules?.[0]).toEqual({
      source: "/(.*)",
      headers: all.filter((h) => h.key !== "Content-Security-Policy"),
    });
    expect(rules?.[1]).toEqual({
      source: staticPolicySource(),
      headers: [
        { key: "Content-Security-Policy", value: contentSecurityPolicy() },
      ],
    });
  });
});

/** Whether next.config's `source` covers `path`, read the way Next reads it. */
function covers(source: string, path: string): boolean {
  return getPathMatch(source, { strict: true })(path) !== false;
}

/** A policy with T-8.7's Razorpay sources taken out, exactly as they're added. */
function withoutRazorpay(policy: string): string {
  // next dev has inline styles of its own; only a Razorpay policy loses them.
  if (!policy.includes("razorpay")) return policy;
  return policy
    .replace(
      " https://checkout.razorpay.com/v1/ https://cdn.razorpay.com/static/",
      "",
    )
    .replace(" https://lumberjack.razorpay.com", "")
    .replace(" https://api.razorpay.com", "")
    .replace("style-src 'self' 'unsafe-inline'; ", "");
}

function withoutSocket(
  policy: string,
  env: Record<string, string | undefined>,
): string {
  const socket = socketOrigin(env);
  return socket ? policy.replace(` ${socket}`, "") : policy;
}

describe("the nonce routes' CSP (T-6.6, D-541)", () => {
  const NONCED = [
    "/login",
    "/onboarding/birthday",
    "/discover",
    "/discover/search",
    "/people/3f0c",
    "/share/priya",
    "/@priya",
    "/@Simran.K",
    "/chats",
    "/wallet",
    "/you",
    "/people/5f0c2b9e-0d1a-4c55-9a43-0c1a2b3c4d5e",
  ];
  const STATIC = [
    "/",
    "/terms",
    "/privacy",
    "/dev/ui",
    "/admin",
    "/discoverx",
    "/peoples",
    "/shared",
    "/@a!b",
    "/@ab",
    "/youth",
    "/peoples",
    "/logins",
    "/robots.txt",
  ];

  it.each(NONCED)("leaves %s to the proxy", (path) => {
    expect(covers(staticPolicySource(), path)).toBe(false);
    expect(proxyConfig.matcher.some((m) => covers(m, path))).toBe(true);
  });

  it.each(STATIC)(
    "gives %s the static policy, and the proxy never sees it",
    (path) => {
      expect(covers(staticPolicySource(), path)).toBe(true);
      expect(proxyConfig.matcher.some((m) => covers(m, path))).toBe(false);
    },
  );

  it("has the proxy match exactly NONCE_ROUTES and all beneath each", () => {
    expect(proxyConfig.matcher).toEqual([
      ...NONCE_ROUTES.map((route) => `/${route}/:path*`),
      AT_USERNAME,
    ]);
  });

  it.each([
    ["local, dev", { NODE_ENV: "development", APP_ENV: "local" }],
    ["ci", { ...STAGING, APP_ENV: "ci" }],
    ["staging", { ...STAGING, APP_ENV: "staging" }],
    ["production", { ...STAGING, APP_ENV: "production" }],
  ])(
    "differs from the static one in script-src, a nonce and 'strict-dynamic', never 'unsafe-inline', and in Razorpay's checkout and the socket alone (%s)",
    (_, env) => {
      const nonced = policyWithNonce(policyWithNonceSlot(env), "Tm9uY2U=");
      const before = contentSecurityPolicy(env).split("; ");
      // Razorpay's sources (T-8.7) and the socket's (T-7.12) are the nonce
      // routes' alone (below).
      const after = withoutSocket(withoutRazorpay(nonced), env).split("; ");

      expect(after).toHaveLength(before.length);
      after.forEach((directive, i) => {
        if (directive.startsWith("script-src")) {
          expect(directive).toContain("'nonce-Tm9uY2U=' 'strict-dynamic'");
          expect(directive).not.toContain("'unsafe-inline'");
          expect(
            directive.replace(
              "'nonce-Tm9uY2U=' 'strict-dynamic'",
              "'unsafe-inline'",
            ),
          ).toBe(before[i]);
        } else {
          expect(directive).toBe(before[i]);
        }
      });
    },
  );

  it("never serves a nonce route under no policy", () => {
    expect(() => policyWithNonce("", "abc")).toThrow(/CSP_WITH_NONCE/);
    expect(() =>
      policyWithNonce(contentSecurityPolicy(STAGING), "abc"),
    ).toThrow();
  });

  it("puts the nonce in every slot", () => {
    expect(policyWithNonce(policyWithNonceSlot(STAGING), "abc")).not.toContain(
      NONCE_SLOT,
    );
  });

  it("makes a fresh 128-bit nonce each time", () => {
    const nonces = new Set(Array.from({ length: 50 }, () => newNonce()));

    expect(nonces.size).toBe(50);
    for (const nonce of nonces) {
      expect(nonce).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    }
  });
});

describe("Razorpay's checkout (T-8.7, D-761): on a Razorpay build's nonce routes, exactly what it asked for", () => {
  it.each(["staging", "production"] as const)(
    "the nonce routes' policy on APP_ENV=%s is exactly this",
    (appEnv) => {
      expect(
        policyWithNonce(
          policyWithNonceSlot({ ...STAGING, APP_ENV: appEnv }),
          "Tm9uY2U=",
        ),
      ).toBe(
        [
          "default-src 'self'",
          "script-src 'self' 'nonce-Tm9uY2U=' 'strict-dynamic' https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/ https://checkout.razorpay.com/v1/ https://cdn.razorpay.com/static/",
          "style-src 'self' 'unsafe-inline'",
          R2_FOR[appEnv].img,
          R2_FOR[appEnv].media,
          `connect-src 'self' https://api.staging.veloraapp.co.in wss://api.staging.veloraapp.co.in ${R2_FOR[appEnv].upload} https://www.google.com/recaptcha/ https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://lumberjack.razorpay.com`,
          "frame-src 'self' https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/ https://api.razorpay.com",
          "worker-src 'self'",
          "object-src 'none'",
          "base-uri 'none'",
          "form-action 'self'",
          "frame-ancestors 'none'",
        ].join("; "),
      );
    },
  );

  it.each(["staging", "production"])(
    "never on the static pages, APP_ENV=%s: nothing there opens a checkout",
    (appEnv) => {
      const csp = contentSecurityPolicy({ ...STAGING, APP_ENV: appEnv });

      expect(csp).not.toContain("razorpay");
      expect(csp).not.toContain("style-src");
    },
  );

  it.each(["local", "ci"])(
    "never on a stand-in build, APP_ENV=%s, nonce routes included: the fake gateway needs nothing",
    (appEnv) => {
      const csp = policyWithNonceSlot({ ...STAGING, APP_ENV: appEnv });

      expect(csp).not.toContain("razorpay");
      expect(csp).not.toContain("style-src");
    },
  );

  it("never on a build with no checkout path", () => {
    expect(policyWithNonceSlot(STAGING)).not.toContain("razorpay");
  });

  it("names Razorpay's hosts, never a wildcard", () => {
    const csp = policyWithNonceSlot({ ...STAGING, APP_ENV: "production" });

    expect(csp).not.toContain("*");
    expect(csp.match(/https:\/\/[a-z.-]*razorpay\.com[^ ;]*/g)).toEqual([
      "https://checkout.razorpay.com/v1/",
      "https://cdn.razorpay.com/static/",
      "https://lumberjack.razorpay.com",
      "https://api.razorpay.com",
    ]);
  });
});

describe("the socket (T-7.12, D-059): the API's own host, on the nonce routes alone", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  function connectSrc(policy: string): string | undefined {
    return policy.split("; ").find((d) => d.startsWith("connect-src"));
  }

  it.each(["staging", "production", "ci"])(
    "adds wss:// for an https:// API on the nonce routes, APP_ENV=%s",
    (appEnv) => {
      const nonced = policyWithNonceSlot({ ...STAGING, APP_ENV: appEnv });

      expect(connectSrc(nonced)).toMatch(
        /^connect-src 'self' https:\/\/api\.staging\.veloraapp\.co\.in wss:\/\/api\.staging\.veloraapp\.co\.in( |$)/,
      );
    },
  );

  it("adds ws:// for the local http:// API under next dev", () => {
    const nonced = policyWithNonceSlot({
      NODE_ENV: "development",
      APP_ENV: "local",
    });

    expect(connectSrc(nonced)).toMatch(
      /^connect-src 'self' http:\/\/127\.0\.0\.1:8000 ws:\/\/127\.0\.0\.1:8000 /,
    );
  });

  it.each(["staging", "production"])(
    "never on the static pages, APP_ENV=%s: nothing there opens a socket",
    (appEnv) => {
      const csp = contentSecurityPolicy({ ...STAGING, APP_ENV: appEnv });

      expect(csp).not.toMatch(/wss?:/);
    },
  );

  it("names no socket when the build has no API, as CI's doesn't", () => {
    expect(socketOrigin({ NODE_ENV: "production" })).toBeNull();
    expect(policyWithNonceSlot({ NODE_ENV: "production" })).not.toMatch(
      /wss?:/,
    );
  });

  it("names exactly the origin ws.ts opens, never a wildcard or another host", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.test/");
    const opened = new URL(socketUrl("t1"));

    expect(socketOrigin()).toBe(`${opened.protocol}//${opened.host}`);
    expect(socketOrigin()).toBe("wss://api.example.test");
  });
});
