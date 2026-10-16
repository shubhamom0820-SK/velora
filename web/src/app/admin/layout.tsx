import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { AdminGate } from "@/components/admin/AdminGate";
import { SessionRestorer } from "@/components/session/SessionRestorer";

/**
 * The moderation panel (T-9.5): signed in and staff, else the 404 page
 * (`AdminGate`, UX only: the API's `require_role` guards the data, D-024).
 * Never in search results, as `(app)` isn't.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

/**
 * Per request, every page beneath: the proxy's nonce (D-541) reaches only a
 * page rendered after the request arrives. `/admin` shows other people's
 * text, so it is one of `NONCE_ROUTES`.
 */
export const dynamic = "force-dynamic";

export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SessionRestorer />
      <AdminGate>
        <AdminFrame>{children}</AdminFrame>
      </AdminGate>
    </>
  );
}
