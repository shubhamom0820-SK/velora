import { t } from "@/i18n/t";

/** Placeholder until the wallet screen (T-5.5). It sits in the app shell's `<main>` (T-5.6). */
export default function WalletPage() {
  return (
    <div className="text-ink flex flex-1 flex-col items-center justify-center gap-2 p-6">
      <h1 className="text-title-1">{t("placeholder.wallet")}</h1>
      <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
    </div>
  );
}
