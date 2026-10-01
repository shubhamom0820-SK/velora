import { ButtonLink } from "@/components/ui/ButtonLink";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

/** The landing page's black header: the plain wordmark and "Get started". */
export function SiteHeader() {
  return (
    <header className="bg-chrome border-chrome-line border-b">
      <div className="mx-auto flex max-w-225 items-center justify-between px-6 py-4">
        <span className="text-title-1 text-chrome-ink tracking-tight">
          {APP_NAME}
        </span>
        <ButtonLink href="/login" size="sm">
          {t("landing.getStarted")}
        </ButtonLink>
      </div>
    </header>
  );
}
