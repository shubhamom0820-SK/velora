import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

/** Placeholder until T-2.1 builds the landing page. */
export default function LandingPage() {
  return (
    <main className="bg-chrome text-chrome-ink flex min-h-dvh flex-col items-center justify-center gap-2 p-6">
      <h1 className="text-display">
        {t("placeholder.marketing", { app: APP_NAME })}
      </h1>
      <p className="text-body text-chrome-mute">
        {t("placeholder.comingSoon")}
      </p>
    </main>
  );
}
