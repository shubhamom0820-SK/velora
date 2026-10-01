import type { ReactNode } from "react";

type LegalFactListProps = {
  facts: ReadonlyArray<{ label: string; value: ReactNode }>;
};

/** Labelled facts — who we are, where to write — as a definition list. */
export function LegalFactList({ facts }: LegalFactListProps) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
      {facts.map(({ label, value }) => (
        <div key={label} className="contents">
          <dt className="text-mute">{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
