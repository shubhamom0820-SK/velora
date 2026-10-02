import { readdirSync } from "node:fs";
import { join } from "node:path";

import type { ResolvingMetadata } from "next";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import { APP_NAME } from "./app";
import {
  PUBLIC_PAGES,
  homeTitle,
  indexable,
  pageMetadata,
  publicPageMetadata,
  robotsFor,
  rootMetadata,
  siteUrl,
  sitemapFor,
} from "./site";

const PRODUCTION = { APP_ENV: "production" };
const NOT_PRODUCTION = [
  { APP_ENV: "staging" },
  { APP_ENV: "ci" },
  { APP_ENV: "local" },
  {},
  // Near misses: an allowlist refuses them, where a blacklist would let them in.
  { APP_ENV: "prod" },
  { APP_ENV: "Production" },
  { APP_ENV: "production " },
];

describe("indexable: only production is indexed (rule 16)", () => {
  it("is true in production", () => {
    expect(indexable(PRODUCTION)).toBe(true);
  });

  it.each(NOT_PRODUCTION)("is false for %j", (env) => {
    expect(indexable(env)).toBe(false);
  });
});

describe("siteUrl", () => {
  it.each([
    [{ APP_ENV: "production" }, "https://veloraapp.co.in"],
    [{ APP_ENV: "staging" }, "https://staging.veloraapp.co.in"],
    [{ APP_ENV: "ci" }, "http://127.0.0.1:3000"],
    [{ APP_ENV: "local" }, "http://127.0.0.1:3000"],
    [{}, "http://127.0.0.1:3000"],
    [{ APP_ENV: "prod" }, "http://127.0.0.1:3000"],
    // Not a lookup on Object.prototype.
    [{ APP_ENV: "constructor" }, "http://127.0.0.1:3000"],
  ])("%j → %s", (env, url) => {
    expect(siteUrl(env)).toBe(url);
  });
});

describe("robots.txt", () => {
  it("in production allows everything and names the sitemap", () => {
    expect(robotsFor(PRODUCTION)).toEqual({
      rules: { userAgent: "*", allow: "/" },
      sitemap: "https://veloraapp.co.in/sitemap.xml",
    });
  });

  it.each(NOT_PRODUCTION)(
    "for %j allows everything and names no sitemap",
    (env) => {
      expect(robotsFor(env)).toEqual({ rules: { userAgent: "*", allow: "/" } });
    },
  );

  // A disallow would stop Google reading a page's noindex, so the page could
  // surface from links elsewhere while we believe it's hidden (robotsFor).
  it.each([PRODUCTION, ...NOT_PRODUCTION])(
    "never disallows a page, for %j",
    (env) => {
      expect(JSON.stringify(robotsFor(env))).not.toMatch(/disallow/i);
    },
  );
});

/** The routes of the pages under src/app/(marketing): "page.tsx" is "/". */
function marketingPagesOnDisk(): string[] {
  const dir = "src/app/(marketing)";
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter((name) => name === "page.tsx" || name.endsWith("/page.tsx"))
    .map((name) => "/" + join(name, "..").replace(/^\.$/, ""))
    .sort();
}

describe("the sitemap", () => {
  it("in production lists every public page on production's address", () => {
    expect(sitemapFor(PRODUCTION)).toEqual([
      { url: "https://veloraapp.co.in/" },
      { url: "https://veloraapp.co.in/terms" },
      { url: "https://veloraapp.co.in/privacy" },
      { url: "https://veloraapp.co.in/refunds" },
      { url: "https://veloraapp.co.in/contact" },
    ]);
  });

  it.each(NOT_PRODUCTION)("is empty for %j", (env) => {
    expect(sitemapFor(env)).toEqual([]);
  });

  it("covers every marketing page on disk, so a new one can't be left out", () => {
    expect([...PUBLIC_PAGES].sort()).toEqual(marketingPagesOnDisk());
  });
});

describe("the root metadata", () => {
  it("in production is indexable, on production's address", () => {
    const metadata = rootMetadata(PRODUCTION);

    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect(metadata.metadataBase?.toString()).toBe("https://veloraapp.co.in/");
  });

  it("on staging is noindex, on staging's address", () => {
    const metadata = rootMetadata({ APP_ENV: "staging" });

    expect(metadata.robots).toEqual({ index: false, follow: false });
    expect(metadata.metadataBase?.toString()).toBe(
      "https://staging.veloraapp.co.in/",
    );
  });

  it("titles pages 'Privacy policy · Velora', and shares as a large card", () => {
    const metadata = rootMetadata(PRODUCTION);

    expect(metadata.title).toEqual({
      default: APP_NAME,
      template: `%s · ${APP_NAME}`,
    });
    expect(metadata.openGraph).toMatchObject({
      type: "website",
      siteName: APP_NAME,
      locale: "en_IN",
    });
    expect(metadata.twitter).toEqual({ card: "summary_large_image" });
  });
});

describe("a public page's metadata", () => {
  it("titles the home page with the brand, then the landing headline", () => {
    expect(homeTitle()).toBe(
      `${APP_NAME} · ${t("landing.headlineThreads")} ${t("landing.headlineKnots")}`,
    );
    expect(pageMetadata("/", homeTitle(), "d").title).toEqual({
      absolute: homeTitle(),
    });
  });

  it("titles the others through the template, and shares the full title", () => {
    const metadata = pageMetadata(
      "/privacy",
      "Privacy policy",
      "What we collect.",
    );

    expect(metadata.title).toBe("Privacy policy");
    expect(metadata.description).toBe("What we collect.");
    expect(metadata.alternates).toEqual({ canonical: "/privacy" });
    expect(metadata.openGraph).toMatchObject({
      title: `Privacy policy · ${APP_NAME}`,
      description: "What we collect.",
      url: "/privacy",
    });
  });

  it("carries the parent's share image forward, its alt text trimmed", async () => {
    const image = {
      url: new URL("https://veloraapp.co.in/opengraph-image.jpg?abc"),
      width: 1200,
      height: 630,
      type: "image/jpeg",
      alt: `${homeTitle()}\n`,
    };
    const parent = Promise.resolve({
      openGraph: { images: [image] },
    }) as unknown as ResolvingMetadata;

    const metadata = await publicPageMetadata(
      "/terms",
      "Terms",
      "Rules.",
    )({}, parent);

    expect(metadata.openGraph?.images).toEqual([
      { ...image, alt: homeTitle() },
    ]);
  });

  it("has no image to carry when the parent has none", async () => {
    const parent = Promise.resolve({
      openGraph: null,
    }) as unknown as ResolvingMetadata;

    const metadata = await publicPageMetadata(
      "/terms",
      "Terms",
      "Rules.",
    )({}, parent);

    expect(metadata.openGraph?.images).toBeUndefined();
  });
});
