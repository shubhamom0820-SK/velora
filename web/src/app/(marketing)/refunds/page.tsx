import { LegalFact } from "@/components/marketing/LegalFact";
import { LegalFactList } from "@/components/marketing/LegalFactList";
import { LegalPage } from "@/components/marketing/LegalPage";
import { LegalSection } from "@/components/marketing/LegalSection";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { LEGAL } from "@/lib/legal";

/**
 * /refunds (T-2.2, D-050): purchases are final, a broken payment is ours to
 * fix, and two cases return Velas on their own. Payment gateways ask for this
 * page before approving a merchant (P-0.8).
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
      <LegalSection title={t("legal.refunds.automatic.title")}>
        <p>{t("legal.refunds.automatic.album")}</p>
        <p>{t("legal.refunds.automatic.banned", { app: APP_NAME })}</p>
      </LegalSection>
    </LegalPage>
  );
}
