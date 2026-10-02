import type { MetadataRoute } from "next";

import { robotsFor } from "@/lib/site";

/** robots.txt (T-2.4). It never disallows a page: see `robotsFor` for why. */
export default function robots(): MetadataRoute.Robots {
  return robotsFor();
}
