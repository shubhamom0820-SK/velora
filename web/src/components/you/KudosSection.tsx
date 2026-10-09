"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { useMyKudos } from "@/lib/queries/kudos";

import { YouSection } from "./YouSection";

/**
 * The kudos you were given (`GET /me/kudos`, D-680): each kind with how many
 * gave it, never who nor when, shown to you whatever `show_kudos` says. The
 * switch is in Privacy and account (T-9.8).
 */
export function KudosSection() {
  const kudos = useMyKudos();
  return (
    <YouSection title={t("you.kudos.title")} body={t("you.kudos.body")}>
      {kudos.isPending ? (
        <Skeleton className="w-2/3" />
      ) : kudos.isError ? (
        <ErrorState
          title={t("you.kudos.failed")}
          onRetry={() => void kudos.refetch()}
        />
      ) : kudos.data.length === 0 ? (
        <p className="text-body text-mute">{t("you.kudos.empty")}</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {kudos.data.map((item) => (
            <li
              key={item.kind}
              className="rounded-pill bg-surface-2 text-ui text-ink px-3 py-1.5"
            >
              {t("you.kudos.count", {
                label: t(`profile.kudosKind.${item.kind}`),
                count: item.count,
              })}
            </li>
          ))}
        </ul>
      )}
    </YouSection>
  );
}
