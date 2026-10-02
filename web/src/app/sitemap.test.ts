import { afterEach, describe, expect, it, vi } from "vitest";

import sitemap from "./sitemap";

// The route reads APP_ENV from the build's environment (src/lib/site.ts has the rules).
describe("/sitemap.xml", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("lists the public pages when the build is production's", () => {
    vi.stubEnv("APP_ENV", "production");

    expect(sitemap().map((entry) => entry.url)).toContain(
      "https://veloraapp.co.in/privacy",
    );
  });

  it("is empty when the build is staging's", () => {
    vi.stubEnv("APP_ENV", "staging");

    expect(sitemap()).toEqual([]);
  });
});
