/**
 * T-9.10's bundle budget, held after every build (CI's web job, after
 * `pnpm build`):
 *
 *     node scripts/bundle-budget.mts        # from web/, after `next build`
 *
 * Every `(app)` route's first-load JavaScript, gzipped, must stay under 250 KB
 * (1 KB = 1,000 bytes, so no rounding helps a route under). Which files a
 * route loads first is Next's own list, written by every build to
 * `.next/diagnostics/route-bundle-stats.json`; each is gzipped here at zlib's
 * default level, the one `next start` serves with. Measured 19 October 2026,
 * those were the very files a phone downloaded for `/discover`, the browser's
 * own requests read beside them (D-1034).
 *
 * The list is Next's internal file, not a documented one, and Next skips a
 * file it can't find without a word. So this fails closed: no list, an
 * `(app)` route missing from it, or a listed file missing from the build is a
 * failure, never a pass with less counted.
 */

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { gzipSync } from "node:zlib";

/** The plan's budget (T-9.10), in bytes: 250 KB, 1 KB = 1,000 bytes. */
export const BUDGET_BYTES = 250_000;

export const STATS = ".next/diagnostics/route-bundle-stats.json";
const APP_GROUP = join("src", "app", "(app)");

type StatsRow = { route: string; firstLoadChunkPaths: string[] };

export type RouteSize = {
  route: string;
  gzipBytes: number;
  files: number;
};

export type Verdict = {
  sizes: RouteSize[];
  /** Every reason this build fails the budget; none means it passes. */
  failures: string[];
};

/**
 * Every route under `(app)`, as Next names it: `src/app/(app)/people/[id]/
 * page.tsx` is `/people/[id]`. A group inside, `(name)`, adds nothing.
 */
export function appRoutes(web: string): string[] {
  const root = join(web, APP_GROUP);
  const routes: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir).sort()) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/^page\.(tsx|ts|jsx|js)$/.test(name)) {
        const segments = relative(root, dir)
          .split(sep)
          .filter((part) => part !== "" && !/^\(.*\)$/.test(part));
        routes.push(`/${segments.join("/")}`);
      }
    }
  };
  walk(root);
  return routes;
}

export function judge(web: string, budget = BUDGET_BYTES): Verdict {
  const failures: string[] = [];
  const statsPath = join(web, STATS);
  if (!existsSync(statsPath)) {
    return {
      sizes: [],
      failures: [`${STATS} is missing: run next build first`],
    };
  }
  const rows = JSON.parse(readFileSync(statsPath, "utf8")) as StatsRow[];
  const routes = appRoutes(web);
  if (routes.length === 0) failures.push(`no page under ${APP_GROUP}`);

  const gzipped = new Map<string, number>();
  const sizes: RouteSize[] = [];
  for (const route of routes) {
    const row = rows.find((one) => one.route === route);
    if (!row) {
      failures.push(`${route}: not in ${STATS}`);
      continue;
    }
    if (row.firstLoadChunkPaths.length === 0) {
      failures.push(`${route}: no first-load files listed`);
      continue;
    }
    let total = 0;
    for (const file of row.firstLoadChunkPaths) {
      const path = join(web, file);
      if (!existsSync(path)) {
        failures.push(`${route}: ${file} is listed but not built`);
        continue;
      }
      let size = gzipped.get(file);
      if (size === undefined) {
        size = gzipSync(readFileSync(path)).length;
        gzipped.set(file, size);
      }
      total += size;
    }
    sizes.push({
      route,
      gzipBytes: total,
      files: row.firstLoadChunkPaths.length,
    });
    if (total >= budget) {
      failures.push(
        `${route}: ${kb(total)} KB gzipped, over the ${kb(budget)} KB budget`,
      );
    }
  }
  return { sizes, failures };
}

export const kb = (bytes: number) => (bytes / 1000).toFixed(1);

export function main(web: string): number {
  const { sizes, failures } = judge(web);
  for (const size of [...sizes].sort((a, b) => b.gzipBytes - a.gzipBytes)) {
    console.log(
      `${size.route.padEnd(24)} ${kb(size.gzipBytes).padStart(6)} KB gzipped, ${size.files} files`,
    );
  }
  if (failures.length > 0) {
    for (const failure of failures) console.error(`FAIL ${failure}`);
    return 1;
  }
  console.log(
    `every (app) route under ${kb(BUDGET_BYTES)} KB gzipped (${sizes.length} ${sizes.length === 1 ? "route" : "routes"})`,
  );
  return 0;
}

if (import.meta.main) {
  process.exitCode = main(join(import.meta.dirname, ".."));
}
