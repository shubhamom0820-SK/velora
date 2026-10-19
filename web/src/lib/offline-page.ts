import { createHash } from "node:crypto";

import { t } from "@/i18n/t";

import { APP_NAME } from "./app";

/**
 * The page the service worker answers with when a page can't be loaded
 * because the network is gone (T-9.7, D-1040). Built at build time, into
 * `/sw.js`, never fetched and never cached: the worker makes it itself.
 *
 * Laid out as the lock screen is (PinLock): `--chrome`, centred, an icon in
 * `--chrome-accent`, a title and a line in `--chrome-mute`. No script at all.
 * Its colours, type and font are `tokens.css` itself, embedded whole, so no
 * value is written here. "Try again" is `href=""`: the page's own address,
 * which is the one that failed, so no URL is ever written into the page.
 */

/**
 * Lucide's `wifi-off` (ISC), as its paths: the page has no React to draw
 * `<WifiOff>` with. `offline-page.test.ts` holds them to lucide-react's own.
 */
export const WIFI_OFF_PATHS: readonly string[] = [
  "M12 20h.01",
  "M8.5 16.429a5 5 0 0 1 7 0",
  "M5 12.859a10 10 0 0 1 5.17-2.69",
  "M19 12.859a10 10 0 0 0-2.007-1.523",
  "M2 8.82a15 15 0 0 1 4.177-2.643",
  "M22 8.82a15 15 0 0 0-11.288-3.764",
  "m2 2 20 20",
];

/** The lock screen's shape, in plain CSS over the tokens. */
const RULES = `
*{box-sizing:border-box}
html,body{margin:0;min-height:100%}
body{min-height:100dvh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 32px;text-align:center;background:var(--chrome);color:var(--chrome-ink);font-family:var(--font-system)}
svg{color:var(--chrome-accent)}
h1{margin:14px 0 0;font-size:var(--type-title-2-size);line-height:var(--type-title-2-line);font-weight:var(--type-title-2-weight)}
p{margin:6px 0 0;max-width:300px;color:var(--chrome-mute);font-size:var(--type-small-size);line-height:var(--type-small-line);font-weight:var(--type-small-weight)}
a{margin-top:32px;padding:12px;color:var(--chrome-accent);font-size:var(--type-ui-size);line-height:var(--type-ui-line);font-weight:600;text-decoration:none}
a:focus-visible{outline:2px solid var(--chrome-accent);outline-offset:2px}
`;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export type OfflinePage = {
  html: string;
  /** Its own policy: nothing loads, and only its one style block applies. */
  csp: string;
};

export function offlinePage(tokensCss: string): OfflinePage {
  const style = `${tokensCss}\n${RULES}`;
  const hash = createHash("sha256").update(style, "utf8").digest("base64");
  const paths = WIFI_OFF_PATHS.map((d) => `<path d="${d}"/>`).join("");
  const title = escapeHtml(t("offline.title"));
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${title} · ${escapeHtml(APP_NAME)}</title>
<style>${style}</style>
</head>
<body>
<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>
<h1>${title}</h1>
<p>${escapeHtml(t("offline.body", { app: APP_NAME }))}</p>
<a href="">${escapeHtml(t("offline.retry"))}</a>
</body>
</html>
`;
  return {
    html,
    csp: `default-src 'none'; style-src 'sha256-${hash}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
  };
}
