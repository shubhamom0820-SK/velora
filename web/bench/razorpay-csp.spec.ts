import { createServer } from "node:http";
import type { AddressInfo } from "node:net";

import { expect, test, type Page } from "@playwright/test";

import { RAZORPAY_SCRIPT } from "../src/lib/razorpay";
import {
  NONCE_SLOT,
  policyWithNonce,
  policyWithNonceSlot,
} from "../src/lib/security-headers";

/**
 * Razorpay's CSP, proved by the browser (T-8.7, D-761). Razorpay publishes no
 * CSP list, so security-headers.ts's RAZORPAY is what its real Checkout asked
 * of the page, and this holds it to that: run by hand, since it fetches
 * Razorpay's live script, never in `make test` or CI.
 *
 *     cd web && pnpm exec playwright test -c bench/razorpay-csp.config.ts
 *
 * A page on loopback, served under the nonce routes' policy exactly as a
 * production build makes it, loads checkout.js the way src/lib/razorpay.ts
 * does and opens it on a key and an order that don't exist: no money can move,
 * and Razorpay's window never shows, but everything it asks of the page is
 * asked. Inside its frame, Razorpay's own policy governs, not ours.
 *
 * Under the policy as served: no violation. Without any one of Razorpay's
 * sources: a violation naming it. So the list is exactly what Checkout needs
 * of a page that hasn't paid, and nothing more. What a real payment asks
 * beyond that (3-D Secure, UPI) is P-661's, with test keys on staging.
 */

const PRODUCTION = {
  APP_ENV: "production",
  NEXT_PUBLIC_API_URL: "https://api.veloraapp.co.in",
};

/** The nonce routes' policy, as production's proxy serves it. */
const SERVED = policyWithNonceSlot(PRODUCTION);

function probePage(nonce: string): string {
  return `<!doctype html><html><head><meta charset="utf-8"><title>probe</title></head><body>
<script nonce="${nonce}">
window.__violations = [];
document.addEventListener("securitypolicyviolation", (e) => {
  window.__violations.push(e.effectiveDirective + " " + e.blockedURI);
});
const s = document.createElement("script");
s.src = ${JSON.stringify(RAZORPAY_SCRIPT)};
s.async = true;
s.onload = () => {
  new window.Razorpay({
    key: "rzp_test_aaaaaaaa",
    order_id: "order_ProbeNotAnOrder",
    amount: 150000,
    currency: "INR",
    name: "Velora",
    description: "30 Velas",
    handler: () => {},
    modal: { ondismiss: () => {} },
  }).open();
  window.__opened = true;
};
document.head.append(s);
</script></body></html>`;
}

type Probe = {
  opened: boolean;
  violations: string[];
  requests: string[];
  frames: string[];
};

/** Serves the probe under `template` (a policy with NONCE_SLOT) and reports. */
async function probe(page: Page, template: string): Promise<Probe> {
  const server = createServer((_req, res) => {
    const nonce = crypto.randomUUID().replaceAll("-", "");
    res.writeHead(200, {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": policyWithNonce(template, nonce),
    });
    res.end(probePage(nonce));
  });
  await new Promise<void>((resolve) =>
    server.listen(0, "127.0.0.1", () => resolve()),
  );
  const { port } = server.address() as AddressInfo;
  const requests = new Set<string>();
  page.on("request", (request) => {
    if (request.frame() === page.mainFrame()) {
      requests.add(`${request.resourceType()} ${request.url().split("?")[0]}`);
    }
  });
  try {
    await page.goto(`http://127.0.0.1:${port}/`);
    await page.waitForTimeout(12_000);
    const result = await page.evaluate(() => {
      const w = window as unknown as {
        __opened?: boolean;
        __violations: string[];
      };
      return { opened: w.__opened === true, violations: w.__violations };
    });
    return {
      opened: result.opened,
      violations: [...new Set(result.violations)].sort(),
      requests: [...requests].sort(),
      frames: page
        .frames()
        .filter((frame) => frame !== page.mainFrame())
        .map((frame) => frame.url().split("?")[0] ?? ""),
    };
  } finally {
    server.close();
  }
}

/** `SERVED` with one source taken out, which must be in it. */
function without(source: string): string {
  expect(SERVED).toContain(source);
  return SERVED.replace(source, "");
}

test("under the policy as served, Checkout opens and nothing is refused", async ({
  page,
}) => {
  const result = await probe(page, SERVED);
  console.log("POLICY", SERVED.replaceAll(NONCE_SLOT, "<nonce>"));
  console.log("REQUESTS", JSON.stringify(result.requests, null, 1));
  console.log("FRAMES", JSON.stringify(result.frames));

  expect(result.opened).toBe(true);
  expect(result.violations).toEqual([]);
  // It really asked: the frame and the logging went out, not nothing at all.
  expect(result.frames).toContain(
    "https://api.razorpay.com/v1/checkout/public",
  );
  expect(
    result.requests.some((r) => r.includes("lumberjack.razorpay.com")),
  ).toBe(true);
});

test.describe("each of Razorpay's sources is needed: without it, the browser refuses", () => {
  test("its frame", async ({ page }) => {
    const result = await probe(page, without(" https://api.razorpay.com"));
    expect(result.violations).toContain("frame-src https://api.razorpay.com");
  });

  test("its logging host", async ({ page }) => {
    const result = await probe(
      page,
      without(" https://lumberjack.razorpay.com"),
    );
    expect(
      result.violations.some((v) =>
        v.startsWith("connect-src https://lumberjack.razorpay.com/"),
      ),
    ).toBe(true);
  });

  test("inline styles: its <style> and its style attributes", async ({
    page,
  }) => {
    const result = await probe(
      page,
      without("style-src 'self' 'unsafe-inline'; "),
    );
    expect(result.violations).toEqual(
      expect.arrayContaining([
        "style-src-elem inline",
        "style-src-attr inline",
      ]),
    );
  });

  test("its two script hosts, in a browser without 'strict-dynamic'", async ({
    page,
  }) => {
    // 'strict-dynamic' admits a script our nonced script adds, and makes host
    // sources ignored; a browser that doesn't know it reads the hosts instead.
    const legacy = SERVED.replace(" 'strict-dynamic'", "");
    expect((await probe(page, legacy)).violations).toEqual([]);

    const result = await probe(
      page,
      legacy.replace(
        " https://checkout.razorpay.com/v1/ https://cdn.razorpay.com/static/",
        "",
      ),
    );
    expect(result.violations).toContain(`script-src-elem ${RAZORPAY_SCRIPT}`);
  });

  test("its risk-detection script, in a browser without 'strict-dynamic'", async ({
    page,
  }) => {
    const legacy = SERVED.replace(" 'strict-dynamic'", "");
    const result = await probe(
      page,
      legacy.replace(" https://cdn.razorpay.com/static/", ""),
    );
    expect(
      result.violations.some((v) =>
        v.startsWith("script-src-elem https://cdn.razorpay.com/static/"),
      ),
    ).toBe(true);
  });
});
