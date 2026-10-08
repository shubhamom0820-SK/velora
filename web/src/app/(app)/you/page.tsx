"use client";

import { ReceivedGifts } from "@/components/gifts/ReceivedGifts";
import { ButtonLink } from "@/components/ui/ButtonLink";
import { t } from "@/i18n/t";
import { useMe } from "@/lib/queries/me";

/**
 * Placeholder until the You tab (T-9.8). It sits in the app shell's `<main>`
 * (T-5.6). Its one link is to your album's requests (T-8.8, D-790), for
 * everyone: a man's album can be asked for too. Hers adds her gifts first
 * (T-8.10): what she received and the switch that shows them on her profile.
 */
export default function YouPage() {
  const woman = useMe().data?.gender === "female";
  const albumRequests = (
    <ButtonLink href="/you/album-requests" variant="ghost" className="mt-4">
      {t("albumRequests.title")}
    </ButtonLink>
  );
  if (!woman) {
    return (
      <div className="text-ink flex flex-1 flex-col items-center justify-center gap-2 p-6">
        <h1 className="text-title-1">{t("placeholder.you")}</h1>
        <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
        {albumRequests}
      </div>
    );
  }
  return (
    <div className="text-ink flex flex-1 flex-col">
      <h1 className="text-title-1 px-(--shell-gutter) pt-5">
        {t("placeholder.you")}
      </h1>
      <ReceivedGifts />
      <div className="flex flex-col items-start gap-2 px-(--shell-gutter) pb-6">
        <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
        {albumRequests}
      </div>
    </div>
  );
}
