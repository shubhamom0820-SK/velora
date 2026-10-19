import type { MetadataRoute } from "next";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { THEME_COLOR } from "@/styles/theme-color";

/**
 * The web app manifest (T-9.7, D-1043), at `/manifest.webmanifest`, which
 * Next links from every page. Static, built once.
 *
 * - `id` is `/`, apart from `start_url`, so moving where the app opens never
 *   makes an installed copy a different app.
 * - `start_url` is `/discover`: the app's first place. Signed out, the gate
 *   sends it to `/login`, as it does any `(app)` route.
 * - Both colours are `--chrome` (theme-color.ts, held to tokens.css): the
 *   splash and the title bar are the header's black.
 * - The icons are `public/icons/`, rendered from tokens.css by
 *   `scripts/render-icons.mts` (08-DESIGN §7); the maskable one keeps its V
 *   inside the centre 80% a launcher may crop to.
 */
const ICONS: MetadataRoute.Manifest["icons"] = [
  { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
  { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
  {
    src: "/icons/icon-maskable-512.png",
    sizes: "512x512",
    type: "image/png",
    purpose: "maskable",
  },
];

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: APP_NAME,
    short_name: APP_NAME,
    description: t("meta.description"),
    lang: "en",
    start_url: "/discover",
    scope: "/",
    display: "standalone",
    theme_color: THEME_COLOR,
    background_color: THEME_COLOR,
    icons: ICONS,
  };
}
