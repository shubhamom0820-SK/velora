import { ButtonLink } from "@/components/ui/ButtonLink";
import { t } from "@/i18n/t";

/**
 * Placeholder until the You tab (T-9.8). It sits in the app shell's `<main>`
 * (T-5.6). Its one link is to your album's requests (T-8.8, D-790), for
 * everyone: a man's album can be asked for too.
 */
export default function YouPage() {
  return (
    <div className="text-ink flex flex-1 flex-col items-center justify-center gap-2 p-6">
      <h1 className="text-title-1">{t("placeholder.you")}</h1>
      <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
      <ButtonLink href="/you/album-requests" variant="ghost" className="mt-4">
        {t("albumRequests.title")}
      </ButtonLink>
    </div>
  );
}
