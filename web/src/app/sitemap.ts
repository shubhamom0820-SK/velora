import type { MetadataRoute } from "next";

import { sitemapFor } from "@/lib/site";

/** sitemap.xml (T-2.4): the public pages in production, empty elsewhere. */
export default function sitemap(): MetadataRoute.Sitemap {
  return sitemapFor();
}
