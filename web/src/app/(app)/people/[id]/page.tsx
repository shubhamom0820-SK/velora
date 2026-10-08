import { t } from "@/i18n/t";

/**
 * Placeholder until T-6.8 builds the in-app profile here, at the one route a
 * profile has (agreed with T-6.8's session, 8 October 2026): the deck's tap
 * (T-6.5), search's rows (T-6.6) and Liked you's tiles (T-6.7) all lead here.
 */
export default function PersonPage() {
  return (
    <div className="text-ink flex flex-1 flex-col items-center justify-center gap-2 p-6">
      <h1 className="text-title-1">{t("placeholder.profile")}</h1>
      <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
    </div>
  );
}
