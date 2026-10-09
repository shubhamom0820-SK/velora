import { describe, expect, it } from "vitest";

import { serviceWorkerSource } from "@/lib/push-worker";

import { GET, dynamic } from "./route";

describe("/sw.js (T-9.4)", () => {
  it("serves the service worker as JavaScript, checked on every visit", async () => {
    const response = GET();

    expect(response.headers.get("Content-Type")).toBe(
      "text/javascript; charset=utf-8",
    );
    expect(response.headers.get("Cache-Control")).toBe("no-cache");
    expect(await response.text()).toBe(serviceWorkerSource());
    expect(dynamic).toBe("force-static");
  });
});
