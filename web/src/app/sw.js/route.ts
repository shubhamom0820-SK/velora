import { serviceWorkerSource } from "@/lib/push-worker";

// Built once, at build time: its words are en.ts's, its tables the app's.
export const dynamic = "force-static";

/**
 * `/sw.js`, the service worker (T-9.4, D-859), at the site's root so its scope
 * is the whole site. `no-cache`: the browser checks for a new one on every
 * visit, so a fix reaches every installed worker at the next.
 */
export function GET(): Response {
  return new Response(serviceWorkerSource(), {
    headers: {
      "Content-Type": "text/javascript; charset=utf-8",
      "Cache-Control": "no-cache",
    },
  });
}
