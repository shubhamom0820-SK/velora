import type { Metadata, MetadataRoute, ResolvingMetadata } from "next";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

/**
 * Where the site lives, whether search engines may index it, and the metadata
 * every page shares (T-2.4). Read from `APP_ENV` at build time, as the legal
 * pages' gate does (D-053).
 */

/** `process.env`, or a stand-in in tests: only `APP_ENV` is read. */
type BuildEnv = Readonly<Record<string, string | undefined>>;

/**
 * Where pages may be indexed: an allowlist (CLAUDE.md rule 16), so a new or
 * misspelt environment is never indexed. Staging is on our real domain (P-33):
 * without this, Google would list it, test data and all, as a copy of production.
 */
const INDEXABLE_IN: ReadonlySet<string> = new Set(["production"]);

const SITE_URLS: ReadonlyMap<string, string> = new Map([
  ["production", "https://veloraapp.co.in"], // D-015
  ["staging", "https://staging.veloraapp.co.in"], // P-33
]);
/** `make dev`'s web address, and where every other build points: never indexed. */
const LOCAL_SITE = "http://127.0.0.1:3000";

/**
 * The pages anyone may land on, and so the sitemap's list. A test checks it
 * against the (marketing) pages on disk, so a new one can't be left out. T-6.8's
 * public profile pages will be public too.
 */
export const PUBLIC_PAGES = [
  "/",
  "/terms",
  "/privacy",
  "/refunds",
  "/contact",
] as const;
export type PublicPage = (typeof PUBLIC_PAGES)[number];

export function indexable(env: BuildEnv = process.env): boolean {
  return env.APP_ENV !== undefined && INDEXABLE_IN.has(env.APP_ENV);
}

export function siteUrl(env: BuildEnv = process.env): string {
  return (env.APP_ENV && SITE_URLS.get(env.APP_ENV)) || LOCAL_SITE;
}

/**
 * robots.txt. It never disallows a page, in any environment.
 *
 * A disallow stops Google fetching the page, so it never reads the page's
 * `noindex`, and the page can still surface in results from links elsewhere
 * while we believe it's hidden. It would also advertise the path (P-30). So a
 * page that mustn't be indexed says `noindex` and stays crawlable: the `(app)`
 * and `(auth)` groups always, and every page outside production. The
 * obvious-looking fix, "just disallow it", is the wrong one.
 */
export function robotsFor(env: BuildEnv = process.env): MetadataRoute.Robots {
  const rules = { userAgent: "*", allow: "/" };
  return indexable(env)
    ? { rules, sitemap: `${siteUrl(env)}/sitemap.xml` }
    : { rules };
}

/** The public pages, on production's address. Empty anywhere else: nothing there is indexed. */
export function sitemapFor(env: BuildEnv = process.env): MetadataRoute.Sitemap {
  if (!indexable(env)) return [];
  return PUBLIC_PAGES.map((path) => ({
    url: new URL(path, siteUrl(env)).toString(),
  }));
}

/** "Privacy policy · Velora": how every page but the home page is titled. */
function titleTemplate(): string {
  return t("meta.titleTemplate", { app: APP_NAME });
}

/**
 * The home page's title: the brand, then the landing headline. The headline
 * promises `app_config.thread_hours`, and so does the share image, whose alt
 * text says exactly this (opengraph-image.alt.txt).
 */
export function homeTitle(): string {
  return t("meta.homeTitle", {
    app: APP_NAME,
    headline: `${t("landing.headlineThreads")} ${t("landing.headlineKnots")}`,
  });
}

const OPEN_GRAPH = {
  type: "website",
  siteName: APP_NAME,
  locale: "en_IN",
} as const;

/**
 * The root layout's metadata. `metadataBase` makes the share image's address
 * absolute on whichever host built it; `robots` is `index` only in production.
 * The share image and the icons come from their files beside the root layout.
 */
export function rootMetadata(env: BuildEnv = process.env): Metadata {
  return {
    metadataBase: new URL(siteUrl(env)),
    title: { default: APP_NAME, template: titleTemplate() },
    description: t("meta.description"),
    openGraph: {
      ...OPEN_GRAPH,
      title: APP_NAME,
      description: t("meta.description"),
    },
    twitter: { card: "summary_large_image" },
    robots: indexable(env)
      ? { index: true, follow: true }
      : { index: false, follow: false },
  };
}

type ShareImages = NonNullable<Metadata["openGraph"]>["images"];

/** One public page's title, description, canonical address and share text. */
export function pageMetadata(
  path: PublicPage,
  title: string,
  description: string,
  images?: ShareImages,
): Metadata {
  const shared = path === "/" ? title : titleTemplate().replace("%s", title);
  return {
    title: path === "/" ? { absolute: title } : title,
    description,
    alternates: { canonical: path },
    openGraph: { ...OPEN_GRAPH, title: shared, description, url: path, images },
  };
}

type ResolvedImage = NonNullable<
  NonNullable<Awaited<ResolvingMetadata>["openGraph"]>["images"]
>[number];

/**
 * The parent's share image, with its alt text trimmed. Next reads the alt from
 * opengraph-image.alt.txt as it is, and the repo's end-of-file hook gives every
 * text file a final newline, which would end up inside `og:image:alt`.
 */
function carriedForward(image: ResolvedImage): ResolvedImage {
  if (typeof image === "string" || image instanceof URL) return image;
  return { ...image, alt: image.alt?.trim() };
}

/**
 * A public page's `generateMetadata`. A page that sets `openGraph` replaces the
 * root's whole `openGraph`, and with it the share image Next attaches from
 * opengraph-image.jpg: T-2.4's first build had no `og:image` on any page. So
 * the page carries its parent's image forward, as Next's docs show, rather than
 * naming the file, which would lose the hash that makes a new image replace the
 * old one in link previews.
 */
export function publicPageMetadata(
  path: PublicPage,
  title: string,
  description: string,
) {
  return async (
    _props: unknown,
    parent: ResolvingMetadata,
  ): Promise<Metadata> => {
    const { openGraph } = await parent;
    const images = openGraph?.images?.map(carriedForward);
    return pageMetadata(path, title, description, images);
  };
}
