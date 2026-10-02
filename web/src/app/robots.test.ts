import { afterEach, describe, expect, it, vi } from "vitest";

import robots from "./robots";

// The route reads APP_ENV from the build's environment (src/lib/site.ts has the rules).
describe("/robots.txt", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("names the sitemap when the build is production's", () => {
    vi.stubEnv("APP_ENV", "production");

    expect(robots().sitemap).toBe("https://veloraapp.co.in/sitemap.xml");
  });

  it("names none when the build is staging's", () => {
    vi.stubEnv("APP_ENV", "staging");

    expect(robots()).toEqual({ rules: { userAgent: "*", allow: "/" } });
  });
});
