import { SignedInRedirect } from "@/components/session/SignedInRedirect";
import { t } from "@/i18n/t";

/** Placeholder until T-3.11's sign-in screens. A restored session moves on. */
export default function LoginPage() {
  return (
    <main className="bg-bg text-ink flex min-h-dvh flex-col items-center justify-center gap-2 p-6">
      <SignedInRedirect />
      <h1 className="text-title-1">{t("placeholder.login")}</h1>
      <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
    </main>
  );
}
