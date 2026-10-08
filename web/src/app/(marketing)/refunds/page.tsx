import { LegalFact } from "@/components/marketing/LegalFact";
import { LegalFactList } from "@/components/marketing/LegalFactList";
import { LegalPage } from "@/components/marketing/LegalPage";
import { LegalSection } from "@/components/marketing/LegalSection";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { LEGAL } from "@/lib/legal";
import { publicPageMetadata } from "@/lib/site";

export const generateMetadata = publicPageMetadata(
  "/refunds",
  t("legal.refunds.title"),
  t("legal.refunds.intro"),
);

/**
 * /refunds (T-2.2, D-050; D-230 by P-130): purchases are final, Velas spent
 * are spent, Velas left in a deleted account are lost (D-504, T-9.6), and a
 * broken payment is ours to fix. Nothing comes back on its own. Payment gateways ask for this page before approving a merchant (P-0.8).
 */
export default function RefundsPage() {
  return (
    <LegalPage
      title={t("legal.refunds.title")}
      intro={t("legal.refunds.intro")}
    >
      <LegalSection title={t("legal.refunds.final.title")}>
        <p>{t("legal.refunds.final.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.refunds.spent.title")}>
        <p>{t("legal.refunds.spent.body", { app: APP_NAME })}</p>
      </LegalSection>
      <LegalSection title={t("legal.refunds.deleted.title")}>
        <p>{t("legal.refunds.deleted.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.refunds.broken.title")}>
        <p>{t("legal.refunds.broken.body")}</p>
        <p>{t("legal.refunds.broken.write")}</p>
        <LegalFactList
          facts={[
            {
              label: t("legal.refunds.broken.support"),
              value: <LegalFact fact={LEGAL.supportEmail} email />,
            },
          ]}
        />
      </LegalSection>
    </LegalPage>
  );
}
