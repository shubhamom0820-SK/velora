import { t } from "@/i18n/t";
import { type Fact, isMissing } from "@/lib/legal";

type LegalFactProps = {
  fact: Fact;
  /** Shows a known value as a mailto link. */
  email?: boolean;
};

/** A legal fact, or "To be confirmed" while we don't have it (D-053). Never an invented value. */
export function LegalFact({ fact, email = false }: LegalFactProps) {
  if (isMissing(fact)) {
    return <em className="text-mute">{t("legal.toBeConfirmed")}</em>;
  }
  if (email) {
    return (
      <a href={`mailto:${fact}`} className="underline underline-offset-2">
        {fact}
      </a>
    );
  }
  return <>{fact}</>;
}
