import { readFileSync } from "node:fs";
import { join } from "node:path";

import { serviceWorkerSource } from "@/lib/push-worker";

// Built once, at build time: its words are en.ts's, its tables the app's, and
// its offline page is drawn with tokens.css itself (T-9.7).
export const dynamic = "force-static";

/** tokens.css, read where `next build` runs: web/. */
function tokensCss(): string {
  return readFileSync(join(process.cwd(), "src/styles/tokens.css"), "utf8");
}

/**
 * `/sw.js`, the service worker (T-9.4, D-859), at the site's root so its scope
 * is the whole site. `no-cache`: the browser checks for a new one on every
 * visit, so a fix reaches every installed worker at the next, and a broken one
 * never sticks on a phone (T-9.7; `register()` asks with `updateViaCache:
 * "none"` for the same reason).
 */
export function GET(): Response {
  return new Response(serviceWorkerSource(tokensCss()), {
    headers: {
      "Content-Type": "text/javascript; charset=utf-8",
      "Cache-Control": "no-cache",
    },
  });
}
