import { t } from "@/i18n/t";

/** Placeholder until the You tab (T-9.8). It sits in the app shell's `<main>` (T-5.6). */
export default function YouPage() {
  return (
    <div className="text-ink flex flex-1 flex-col items-center justify-center gap-2 p-6">
      <h1 className="text-title-1">{t("placeholder.you")}</h1>
      <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
    </div>
  );
}
