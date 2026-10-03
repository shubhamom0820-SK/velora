import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppGate } from "@/components/session/AppGate";
import { SessionRestorer } from "@/components/session/SessionRestorer";

/**
 * Every page in the app is behind sign-in and never belongs in search results.
 * `noindex` here covers every route added under `(app)` later, without anyone
 * editing robots.txt. It must stay crawlable: a robots.txt disallow would stop
 * Google reading this `noindex` (src/lib/site.ts, `robotsFor`).
 *
 * This layout restores the session, requires onboarding `done`, and shows the
 * PIN lock (T-3.10). T-5.6 adds the header and nav inside `AppGate`, never
 * replacing it.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SessionRestorer />
      <AppGate>{children}</AppGate>
    </>
  );
}
