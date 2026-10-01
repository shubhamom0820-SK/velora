import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { assertLegalFactsComplete, missingFacts } from "@/lib/legal";

type LegalPageProps = { title: string; intro: string; children: ReactNode };

/**
 * One legal page (T-2.2), from the prototype's legal view: a back link, the
 * title, then its sections, 720 px wide (08-DESIGN §3). Rendering it checks
 * the legal facts, and the pages are static, so a build that may not show a
 * missing fact fails here (D-053). Printing drops the back link (the layout
 * drops the footer), so a printed page is the policy alone.
 */
export function LegalPage({ title, intro, children }: LegalPageProps) {
  assertLegalFactsComplete();
  const unfinished = missingFacts().length > 0;

  return (
    <main className="mx-auto w-full max-w-180 flex-1 px-6 py-8 print:max-w-none print:px-0">
      {/* The invisible ::before stretches the tap area past 44 px (08-DESIGN §3). */}
      <Link
        href="/"
        className="text-ui text-mute relative inline-flex items-center gap-1 before:absolute before:-inset-x-2 before:-inset-y-3 print:hidden"
      >
        <Icon icon={ChevronLeft} size={18} />
        {t("legal.back")}
      </Link>
      <h1 className="text-title-1 text-ink mt-6">{title}</h1>
      <p className="text-body text-ink mt-3">{intro}</p>
      {unfinished && (
        <p className="text-small text-ink border-line bg-surface rounded-card mt-4 border px-4 py-3">
          {t("legal.notFinal")}
        </p>
      )}
      <div className="mt-8 flex flex-col gap-8">{children}</div>
    </main>
  );
}
