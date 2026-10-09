"use client";

import { ReceivedGifts } from "@/components/gifts/ReceivedGifts";
import { ButtonLink } from "@/components/ui/ButtonLink";
import { t } from "@/i18n/t";
import { useMe } from "@/lib/queries/me";

/**
 * Placeholder until the You tab (T-9.8). It sits in the app shell's `<main>`
 * (T-5.6). Its links: your album's requests (T-8.8, D-790), for everyone, a
 * man's album can be asked for too; and your notifications and their
 * settings (T-9.4, D-859), until T-9.8's settings rows take them. Hers adds
 * her gifts first (T-8.10): what she received and the switch that shows them
 * on her profile.
 */
export default function YouPage() {
  const woman = useMe().data?.gender === "female";
  const links = (
    <div className="mt-4 flex flex-col gap-2">
      <ButtonLink href="/you/album-requests" variant="ghost">
        {t("albumRequests.title")}
      </ButtonLink>
      <ButtonLink href="/notifications" variant="ghost">
        {t("notifications.you.list")}
      </ButtonLink>
      <ButtonLink href="/you/notifications" variant="ghost">
        {t("notifications.you.settings")}
      </ButtonLink>
    </div>
  );
  if (!woman) {
    return (
      <div className="text-ink flex flex-1 flex-col items-center justify-center gap-2 p-6">
        <h1 className="text-title-1">{t("placeholder.you")}</h1>
        <p className="text-body text-mute">{t("placeholder.comingSoon")}</p>
        {links}
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
        {links}
      </div>
    </div>
  );
}
