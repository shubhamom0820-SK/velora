import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { serviceWorkerSource } from "@/lib/push-worker";

import { GET, dynamic } from "./route";

describe("/sw.js (T-9.4)", () => {
  it("serves the service worker as JavaScript, checked on every visit", async () => {
    const response = GET();

    expect(response.headers.get("Content-Type")).toBe(
      "text/javascript; charset=utf-8",
    );
    // A broken worker never sticks on a phone (T-9.7): the browser asks
    // again on every visit, never from its HTTP cache.
    expect(response.headers.get("Cache-Control")).toBe("no-cache");
    expect(await response.text()).toBe(
      serviceWorkerSource(readFileSync("src/styles/tokens.css", "utf8")),
    );
    expect(dynamic).toBe("force-static");
  });

  it("draws its offline page with tokens.css itself (T-9.7)", async () => {
    const source = await GET().text();
    const tokens = readFileSync("src/styles/tokens.css", "utf8");
    expect(source).toContain(JSON.stringify(tokens).slice(1, -1));
  });
});
