// @vitest-environment node
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { CASES } from "../../scripts/break-guards.mjs";

// The breaking-run script (scripts/break-guards.mts) stays runnable: every
// case's anchor is still in its file exactly once, and every test file it runs
// is still there. Without this, an edit to a guarded file would leave a case
// that can't apply, and T-4.6's claim that each guard goes red unrecheckable.
const WEB = process.cwd();

describe("the web's breaking runs (T-4.6)", () => {
  it.each(CASES.map((c) => [c.id, c] as const))(
    "%s can still apply",
    (_, found) => {
      const text = readFileSync(join(WEB, found.file), "utf8");

      expect(text.split(found.old)).toHaveLength(2);
      expect(found.new).not.toBe(found.old);
      expect(found.expect.length).toBeGreaterThan(0);
      for (const file of found.run)
        expect(existsSync(join(WEB, file))).toBe(true);
    },
  );

  it("names each case once, by its task", () => {
    const ids = CASES.map((c) => c.id);

    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.every((id) => /^t(?:4(?:[5-8]|12)|811|66)-/.test(id))).toBe(
      true,
    );
  });
});
