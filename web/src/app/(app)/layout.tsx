import type { Metadata } from "next";
import type { ReactNode } from "react";

/**
 * Every page in the app is behind sign-in and never belongs in search results.
 * `noindex` here covers every route added under `(app)` later, without anyone
 * editing robots.txt. It must stay crawlable: a robots.txt disallow would stop
 * Google reading this `noindex` (src/lib/site.ts, `robotsFor`).
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return children;
}
