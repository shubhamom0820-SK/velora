import type { Metadata } from "next";
import type { ReactNode } from "react";

/**
 * Sign-in pages aren't destinations, so they stay out of search results. As
 * with `(app)`, the `noindex` covers every route added here later, and the
 * pages must stay crawlable for Google to read it (src/lib/site.ts, `robotsFor`).
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AuthGroupLayout({ children }: { children: ReactNode }) {
  return children;
}
