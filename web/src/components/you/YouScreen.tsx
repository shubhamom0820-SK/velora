"use client";

import { ReceivedGifts } from "@/components/gifts/ReceivedGifts";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { useMe } from "@/lib/queries/me";

import { BlockedSection } from "./BlockedSection";
import { ClearedSection } from "./ClearedSection";
import { KnotsSection } from "./KnotsSection";
import { KudosSection } from "./KudosSection";
import { ProfileSummary } from "./ProfileSummary";
import { ReportsSection } from "./ReportsSection";
import { YouRows } from "./YouRows";

/**
 * The You tab (T-9.8), inside the app shell's `<main>` (T-5.6), from existing
 * parts (D-913), in the prototype's order: who you are, your kudos, her gifts
 * (T-8.10, hers alone), your Knots, whom you block, your reports, your cleared
 * chats, then the settings rows, lock and sign out. No invite or referral
 * card while referrals are paused (D-840). Each section loads, fails and is
 * empty on its own, so one slow list never holds up the rest.
 */
export function YouScreen() {
  const me = useMe();
  if (me.isPending) {
    return (
      <div aria-busy className="flex flex-col gap-3 p-(--shell-gutter)">
        <h1 className="sr-only">{t("you.title")}</h1>
        <Skeleton variant="avatar" />
        <Skeleton className="w-2/3" />
        <Skeleton className="w-1/2" />
      </div>
    );
  }
  if (me.isError) {
    return (
      <div className="p-(--shell-gutter)">
        <h1 className="sr-only">{t("you.title")}</h1>
        <ErrorState
          title={t("you.summaryFailed")}
          onRetry={() => void me.refetch()}
        />
      </div>
    );
  }
  const woman = me.data.gender === "female";
  return (
    <div className="text-ink flex flex-1 flex-col pb-6">
      <h1 className="sr-only">{t("you.title")}</h1>
      <ProfileSummary me={me.data} />
      <KudosSection />
      {woman && <ReceivedGifts />}
      <KnotsSection />
      <BlockedSection />
      <ReportsSection />
      <ClearedSection />
      <YouRows me={me.data} />
    </div>
  );
}
