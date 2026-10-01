import type { ReactNode } from "react";

type LegalSectionProps = { title: string; children: ReactNode };

/**
 * One titled section of a legal page; its paragraphs and lists take the body
 * type. Printed whole where it fits, so a heading never ends a page alone.
 */
export function LegalSection({ title, children }: LegalSectionProps) {
  return (
    <section className="text-body text-ink flex flex-col gap-3 print:break-inside-avoid">
      <h2 className="text-title-2">{title}</h2>
      {children}
    </section>
  );
}
