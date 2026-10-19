// @vitest-environment node
import { randomBytes } from "node:crypto";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { gzipSync } from "node:zlib";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  appRoutes,
  BUDGET_BYTES,
  judge,
  main,
  STATS,
} from "../../scripts/bundle-budget.mjs";

// T-9.10's budget check (scripts/bundle-budget.mts), on builds made here: a
// web directory with pages, Next's list and chunks of known size. Random
// bytes barely compress, so a chunk's gzipped size is what the test chose.

const made: string[] = [];

afterEach(() => {
  for (const dir of made.splice(0)) rmSync(dir, { recursive: true });
  vi.restoreAllMocks();
});

type Build = {
  pages: string[];
  stats?: { route: string; firstLoadChunkPaths: string[] }[];
  chunks?: Record<string, Buffer>;
};

function build({ pages, stats, chunks = {} }: Build): string {
  const web = mkdtempSync(join(tmpdir(), "bundle-budget-"));
  made.push(web);
  for (const page of pages) {
    const path = join(web, "src/app", page);
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, "export default function Page() {}\n");
  }
  for (const [file, bytes] of Object.entries(chunks)) {
    mkdirSync(dirname(join(web, file)), { recursive: true });
    writeFileSync(join(web, file), bytes);
  }
  if (stats) {
    mkdirSync(dirname(join(web, STATS)), { recursive: true });
    writeFileSync(join(web, STATS), JSON.stringify(stats));
  }
  return web;
}

const chunk = (name: string) => `.next/static/chunks/${name}.js`;

/** Incompressible bytes whose gzip is `target` bytes, give or take nothing. */
function gzippedTo(target: number): Buffer {
  let size = target;
  for (;;) {
    const bytes = randomBytes(size);
    const over = gzipSync(bytes).length - target;
    if (over === 0) return bytes;
    size -= over;
  }
}

describe("the (app) routes, as Next names them", () => {
  it("lists every page under (app), and only those", () => {
    const routes = appRoutes(process.cwd());

    expect(routes).toEqual(
      expect.arrayContaining([
        "/discover",
        "/discover/likes",
        "/chats/[id]",
        "/people/[id]",
        "/you/settings",
        "/wallet",
      ]),
    );
    expect(routes).not.toContain("/login");
    expect(routes).not.toContain("/");
    expect(routes).not.toContain("/admin");
  });

  it("leaves a group's name out of the route", () => {
    const web = build({
      pages: ["(app)/discover/page.tsx", "(app)/(inner)/wallet/page.tsx"],
    });

    expect(appRoutes(web).sort()).toEqual(["/discover", "/wallet"]);
  });
});

describe("the budget: every (app) route under 250 KB gzipped (T-9.10)", () => {
  it("is 250 KB of 1,000 bytes, the plan's number", () => {
    expect(BUDGET_BYTES).toBe(250_000);
  });

  it("passes a build whose routes are under it, counting a shared file in each", () => {
    const web = build({
      pages: ["(app)/discover/page.tsx", "(app)/wallet/page.tsx"],
      stats: [
        { route: "/discover", firstLoadChunkPaths: [chunk("a"), chunk("b")] },
        { route: "/wallet", firstLoadChunkPaths: [chunk("a")] },
      ],
      chunks: { [chunk("a")]: gzippedTo(1000), [chunk("b")]: gzippedTo(500) },
    });

    const verdict = judge(web);

    expect(verdict.failures).toEqual([]);
    expect(verdict.sizes).toEqual([
      { route: "/discover", gzipBytes: 1500, files: 2 },
      { route: "/wallet", gzipBytes: 1000, files: 1 },
    ]);
  });

  it("fails a route at the budget or over it, naming it and its size", () => {
    const web = build({
      pages: ["(app)/discover/page.tsx", "(app)/wallet/page.tsx"],
      stats: [
        { route: "/discover", firstLoadChunkPaths: [chunk("a"), chunk("b")] },
        { route: "/wallet", firstLoadChunkPaths: [chunk("a")] },
      ],
      chunks: { [chunk("a")]: gzippedTo(600), [chunk("b")]: gzippedTo(400) },
    });

    expect(judge(web, 1000).failures).toEqual([
      "/discover: 1.0 KB gzipped, over the 1.0 KB budget",
    ]);
    expect(judge(web, 1001).failures).toEqual([]);
  });

  it("fails closed with no list: never a pass with nothing counted", () => {
    const web = build({ pages: ["(app)/discover/page.tsx"] });

    expect(judge(web).failures).toEqual([
      `${STATS} is missing: run next build first`,
    ]);
  });

  it("fails an (app) route the list leaves out", () => {
    const web = build({
      pages: ["(app)/discover/page.tsx", "(app)/wallet/page.tsx"],
      stats: [{ route: "/discover", firstLoadChunkPaths: [chunk("a")] }],
      chunks: { [chunk("a")]: gzippedTo(100) },
    });

    expect(judge(web).failures).toEqual([`/wallet: not in ${STATS}`]);
  });

  it("fails a listed file the build doesn't have, which Next skips without a word", () => {
    const web = build({
      pages: ["(app)/discover/page.tsx"],
      stats: [
        {
          route: "/discover",
          firstLoadChunkPaths: [chunk("a"), chunk("gone")],
        },
      ],
      chunks: { [chunk("a")]: gzippedTo(100) },
    });

    expect(judge(web).failures).toEqual([
      `/discover: ${chunk("gone")} is listed but not built`,
    ]);
  });

  it("fails a route listed with no files at all", () => {
    const web = build({
      pages: ["(app)/discover/page.tsx"],
      stats: [{ route: "/discover", firstLoadChunkPaths: [] }],
    });

    expect(judge(web).failures).toEqual([
      "/discover: no first-load files listed",
    ]);
  });

  it("exits 1 and says why when a route is over; 0 with each size when none is", () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const logs = vi.spyOn(console, "log").mockImplementation(() => {});
    const over = build({
      pages: ["(app)/discover/page.tsx"],
      stats: [{ route: "/discover", firstLoadChunkPaths: [chunk("a")] }],
      chunks: { [chunk("a")]: gzippedTo(BUDGET_BYTES + 100) },
    });

    expect(main(over)).toBe(1);
    expect(errors).toHaveBeenCalledWith(
      "FAIL /discover: 250.1 KB gzipped, over the 250.0 KB budget",
    );

    const under = build({
      pages: ["(app)/discover/page.tsx"],
      stats: [{ route: "/discover", firstLoadChunkPaths: [chunk("a")] }],
      chunks: { [chunk("a")]: gzippedTo(249_000) },
    });
    errors.mockClear();
    expect(main(under)).toBe(0);
    expect(errors).not.toHaveBeenCalled();
    expect(logs).toHaveBeenCalledWith(
      "every (app) route under 250.0 KB gzipped (1 route)",
    );
  });
});
