import type { ReactNode } from "react";

import { SiteFooter } from "@/components/marketing/SiteFooter";

/** Every marketing page — the landing page and the legal pages — ends in the same footer (T-2.2). */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-bg flex min-h-dvh flex-col print:min-h-0 print:bg-transparent">
      {children}
      <SiteFooter />
    </div>
  );
}
