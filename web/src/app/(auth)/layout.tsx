import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SessionRestorer } from "@/components/session/SessionRestorer";

/**
 * Sign-in pages aren't destinations, so they stay out of search results. As
 * with `(app)`, the `noindex` covers every route added here later, and the
 * pages must stay crawlable for Google to read it (src/lib/site.ts, `robotsFor`).
 *
 * The session is restored from here and `(app)`'s layout, never a marketing
 * page (T-3.10). /login doesn't wait for it, except to send a code (D-950);
 * onboarding's own layout does.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

/**
 * Per request, every page beneath: the proxy's nonce (D-541) reaches only a
 * page rendered after the request arrives, never one built ahead of it.
 */
export const dynamic = "force-dynamic";

export default function AuthGroupLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SessionRestorer />
      {children}
    </>
  );
}
