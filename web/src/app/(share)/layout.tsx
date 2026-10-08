import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/marketing/SiteFooter";
import { SessionRestorer } from "@/components/session/SessionRestorer";

/**
 * `/@username`'s page (T-6.8, D-544), served here through next.config's
 * rewrite: an `@` never begins a route segment (D-068). Its own group, not
 * `(marketing)`, because it restores a session, which a marketing page never
 * does (T-3.10): someone signed in is sent to the in-app profile.
 *
 * Never indexed, whatever the environment: a person's page is theirs to
 * share, not a search result. Rendered per request, both for the proxy's
 * nonce (D-541) and so a link turned off, or a profile hidden, shows nothing
 * from the moment it is.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export const dynamic = "force-dynamic";

export default function ShareGroupLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="bg-bg flex min-h-dvh flex-col">
      <SessionRestorer />
      {children}
      <SiteFooter />
    </div>
  );
}
