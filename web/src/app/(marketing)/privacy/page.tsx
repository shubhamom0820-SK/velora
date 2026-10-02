import { LegalFact } from "@/components/marketing/LegalFact";
import { LegalFactList } from "@/components/marketing/LegalFactList";
import { LegalPage } from "@/components/marketing/LegalPage";
import { LegalSection } from "@/components/marketing/LegalSection";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { LEGAL } from "@/lib/legal";

const COLLECTED = [
  "phone",
  "birth",
  "gender",
  "profile",
  "location",
  "photos",
  "selfie",
  "messages",
  "payments",
  "waitlist",
] as const;

const WHERE = [
  "database",
  "waitlist",
  "servers",
  "media",
  "moderation",
  "faceMatch",
  "phone",
] as const;

const DELETION = ["erased", "messages", "kept", "google"] as const;

/**
 * /privacy (T-2.2): what we collect, where it is, who else handles it, and what
 * deleting an account keeps. Google's copy of the phone number comes first, on
 * purpose (D-048): a reader must not discover it later.
 */
export default function PrivacyPage() {
  const app = { app: APP_NAME };

  return (
    <LegalPage
      title={t("legal.privacy.title")}
      intro={t("legal.privacy.intro", app)}
    >
      <LegalSection title={t("legal.privacy.google.title")}>
        <p>{t("legal.privacy.google.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.privacy.collect.title")}>
        <ul className="flex list-disc flex-col gap-2 pl-5">
          {COLLECTED.map((key) => (
            <li key={key}>{t(`legal.privacy.collect.${key}`, app)}</li>
          ))}
        </ul>
      </LegalSection>
      <LegalSection title={t("legal.privacy.where.title")}>
        <ul className="flex list-disc flex-col gap-2 pl-5">
          {WHERE.map((key) => (
            <li key={key}>{t(`legal.privacy.where.${key}`)}</li>
          ))}
        </ul>
      </LegalSection>
      <LegalSection title={t("legal.privacy.others.title")}>
        <p>{t("legal.privacy.others.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.privacy.cookies.title")}>
        <p>{t("legal.privacy.cookies.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.privacy.choices.title")}>
        <p>{t("legal.privacy.choices.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.privacy.deletion.title")}>
        {DELETION.map((key) => (
          <p key={key}>{t(`legal.privacy.deletion.${key}`)}</p>
        ))}
      </LegalSection>
      <LegalSection title={t("legal.privacy.children.title")}>
        <p>{t("legal.privacy.children.body", app)}</p>
      </LegalSection>
      <LegalSection title={t("legal.privacy.grievance.title")}>
        <p>{t("legal.privacy.grievance.body")}</p>
        <LegalFactList
          facts={[
            {
              label: t("legal.privacy.grievance.officer"),
              value: <LegalFact fact={LEGAL.grievanceOfficerName} />,
            },
            {
              label: t("legal.privacy.grievance.email"),
              value: <LegalFact fact={LEGAL.grievanceOfficerEmail} email />,
            },
          ]}
        />
      </LegalSection>
    </LegalPage>
  );
}
