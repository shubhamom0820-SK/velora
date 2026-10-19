import type { Metadata } from "next";
import type { ReactNode } from "react";

import { InstallBanner } from "@/components/pwa/InstallBanner";
import { Realtime } from "@/components/realtime/Realtime";
import { AppGate } from "@/components/session/AppGate";
import { SessionRestorer } from "@/components/session/SessionRestorer";
import { AppShell } from "@/components/shell/AppShell";
import { StoreSheet } from "@/components/wallet/StoreSheet";

/**
 * Every page in the app is behind sign-in and never belongs in search results.
 * `noindex` here covers every route added under `(app)` later, without anyone
 * editing robots.txt. It must stay crawlable: a robots.txt disallow would stop
 * Google reading this `noindex` (src/lib/site.ts, `robotsFor`).
 *
 * This layout restores the session, requires onboarding `done`, and shows the
 * PIN lock (T-3.10). The header and nav (T-5.6) sit inside `AppGate`, so they
 * appear only once the gate lets someone in, and the lock covers them too. So
 * does the store sheet (T-5.5), which any screen's mutation can open, and the
 * socket (T-7.12), open only while someone is let in. The install banner
 * (T-9.7) is the first thing on every screen, under the header, as the
 * prototype draws it.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

/**
 * Per request, every page beneath: the proxy's nonce (D-541) reaches only a
 * page rendered after the request arrives, never one built ahead of it.
 */
export const dynamic = "force-dynamic";

export default function AppGroupLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SessionRestorer />
      <AppGate>
        <AppShell>
          <InstallBanner />
          {children}
        </AppShell>
        <StoreSheet />
        <Realtime />
      </AppGate>
    </>
  );
}
