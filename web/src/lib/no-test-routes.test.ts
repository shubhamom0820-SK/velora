// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

// The API's local-only test routes (`/v1/test/...`: a sign-in code, a Thread's
// hour run out, a fake payment's webhook, a person made staff, D-963) are the
// E2E's, called from Node in `e2e/`, never by the app: nothing the browser
// downloads names one (T-9.11). They are never in OpenAPI, so `api.ts` has no
// type for them; this holds the source too, every file under src/ that isn't
// a test, where a path could be written out by hand.

const SRC = new URL("..", import.meta.url).pathname;

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sources(path);
    if (!/\.(ts|tsx|js|mjs)$/.test(entry.name)) return [];
    if (/\.test\.(ts|tsx)$/.test(entry.name)) return [];
    return [path];
  });
}

// `/test/` as a path segment, with or without `/v1` before it.
const TEST_ROUTE = /["'`]\s*(?:\/v1)?\/test\//;

describe("the app never calls a test route (T-9.11, D-963)", () => {
  it("finds the source it scans", () => {
    // A scan of nothing passes everything: it must see the app's own files.
    const scanned = sources(SRC).map((path) => relative(SRC, path));
    expect(scanned).toContain("lib/api.ts");
    expect(scanned.length).toBeGreaterThan(100);
  });

  it("matches a test route however it is written", () => {
    for (const written of [
      `"/v1/test/users/1/role"`,
      "`/v1/test/users/${id}/role`",
      `'/test/sms/last-code'`,
    ]) {
      expect(written).toMatch(TEST_ROUTE);
    }
  });

  it("names no test route anywhere under src/", () => {
    const naming = sources(SRC)
      .filter((path) => TEST_ROUTE.test(readFileSync(path, "utf8")))
      .map((path) => relative(SRC, path));
    expect(naming).toEqual([]);
  });
});
