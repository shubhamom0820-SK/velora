// @vitest-environment node
import { readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

import { WALKED_ROOTS, WALKED_ROUTES } from "../../e2e/a11y-routes";

// T-9.11: every signed-in screen is walked by axe and the keyboard
// (e2e/a11y.spec.ts). The walk's list is held to the page files that exist,
// exactly: a new `(app)` or admin screen fails here until it is walked, and a
// walked route whose page has gone fails too.

const APP = new URL("../app", import.meta.url).pathname;

function pages(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return pages(path);
    return entry.name === "page.tsx" ? [relative(APP, path)] : [];
  });
}

describe("the accessibility walk's routes (T-9.11)", () => {
  it("are exactly the (app) and admin pages", () => {
    const existing = WALKED_ROOTS.flatMap((root) => pages(join(APP, root)));
    // A scan of nothing would match an empty list: both roots have pages.
    expect(existing).toContain("(app)/discover/page.tsx");
    expect(existing).toContain("admin/page.tsx");

    expect(WALKED_ROUTES.map((route) => route.page).sort()).toEqual(
      existing.sort(),
    );
  });

  it("walks each (app) page as him and as her, and each admin page as staff", () => {
    for (const { page, walkers } of WALKED_ROUTES) {
      expect([...walkers].sort(), page).toEqual(
        page.startsWith("admin/") ? ["staff"] : ["her", "him"],
      );
    }
  });

  it("puts every walked route at a path of its own", () => {
    const ids = { thread: "t", other: "o", her: "h" };
    const paths = WALKED_ROUTES.map((route) => route.path(ids));
    expect(new Set(paths).size).toBe(paths.length);
  });
});
