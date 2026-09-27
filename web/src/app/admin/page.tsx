import { t } from "@/i18n/t";

/** Placeholder until the admin panel (T-9.5). */
export default function AdminPage() {
  return (
    <main className="bg-bg text-ink flex min-h-dvh flex-col items-center justify-center gap-2 p-6">
      <h1 className="text-title-1">{t("placeholder.admin")}</h1>
      <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
    </main>
  );
}
