import Link from "next/link";

import { LegalFact } from "@/components/marketing/LegalFact";
import { LegalFactList } from "@/components/marketing/LegalFactList";
import { LegalPage } from "@/components/marketing/LegalPage";
import { LegalSection } from "@/components/marketing/LegalSection";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { LEGAL, PLACE } from "@/lib/legal";

const LINK = "underline underline-offset-2";

/** /terms (T-2.2): the rules for using the app, each from a decision (comments in en.ts). */
export default function TermsPage() {
  const app = { app: APP_NAME };

  return (
    <LegalPage
      title={t("legal.terms.title")}
      intro={t("legal.terms.intro", app)}
    >
      <LegalSection title={t("legal.terms.whoWeAre.title")}>
        <p>{t("legal.terms.whoWeAre.body", { ...app, ...PLACE })}</p>
      </LegalSection>
      <LegalSection title={t("legal.terms.whoCanJoin.title", app)}>
        <p>{t("legal.terms.whoCanJoin.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.terms.conversations.title")}>
        <p>{t("legal.terms.conversations.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.terms.paying.title")}>
        <p>{t("legal.terms.paying.prices", app)}</p>
        <p>{t("legal.terms.paying.velas")}</p>
        <p>
          <Link href="/refunds" className={LINK}>
            {t("legal.links.refunds")}
          </Link>
        </p>
      </LegalSection>
      <LegalSection title={t("legal.terms.profile.title")}>
        <p>{t("legal.terms.profile.body", app)}</p>
      </LegalSection>
      <LegalSection title={t("legal.terms.safety.title")}>
        <p>{t("legal.terms.safety.messages")}</p>
        <p>{t("legal.terms.safety.reports", app)}</p>
      </LegalSection>
      <LegalSection title={t("legal.terms.promises.title")}>
        <p>{t("legal.terms.promises.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.terms.screenshots.title")}>
        <p>{t("legal.terms.screenshots.body")}</p>
      </LegalSection>
      <LegalSection title={t("legal.terms.chats.title")}>
        <p>{t("legal.terms.chats.body")}</p>
        <p>
          <Link href="/privacy" className={LINK}>
            {t("legal.links.privacy")}
          </Link>
        </p>
      </LegalSection>
      <LegalSection title={t("legal.terms.law.title")}>
        <p>{t("legal.terms.law.body", PLACE)}</p>
        <LegalFactList
          facts={[
            {
              label: t("legal.terms.law.court"),
              value: <LegalFact fact={LEGAL.court} />,
            },
          ]}
        />
      </LegalSection>
      <LegalSection title={t("legal.terms.questions.title")}>
        <p>{t("legal.terms.questions.body")}</p>
        <p>
          <Link href="/contact" className={LINK}>
            {t("legal.links.contact")}
          </Link>
        </p>
      </LegalSection>
    </LegalPage>
  );
}
