import { LegalFact } from "@/components/marketing/LegalFact";
import { LegalFactList } from "@/components/marketing/LegalFactList";
import { LegalPage } from "@/components/marketing/LegalPage";
import { LegalSection } from "@/components/marketing/LegalSection";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { LEGAL, PLACE } from "@/lib/legal";

/**
 * /contact (T-2.2): who runs the app and who handles complaints (IT Rules).
 * Each fact comes from src/lib/legal.ts; the city is decided (D-013), the rest
 * waits on registration and the domain (D-053).
 */
export default function ContactPage() {
  return (
    <LegalPage
      title={t("legal.contact.title")}
      intro={t("legal.contact.intro", { app: APP_NAME })}
    >
      <LegalSection title={t("legal.contact.details")}>
        <LegalFactList
          facts={[
            {
              label: t("legal.contact.company"),
              value: <LegalFact fact={LEGAL.companyName} />,
            },
            {
              label: t("legal.contact.office"),
              value: (
                <>
                  <LegalFact fact={LEGAL.registeredOffice} />
                  <br />
                  {t("legal.contact.place", PLACE)}
                </>
              ),
            },
            {
              label: t("legal.contact.support"),
              value: <LegalFact fact={LEGAL.supportEmail} email />,
            },
            {
              label: t("legal.contact.grievanceOfficer"),
              value: <LegalFact fact={LEGAL.grievanceOfficerName} />,
            },
            {
              label: t("legal.contact.grievanceEmail"),
              value: <LegalFact fact={LEGAL.grievanceOfficerEmail} email />,
            },
          ]}
        />
        <p>{t("legal.contact.timelines")}</p>
      </LegalSection>
    </LegalPage>
  );
}
