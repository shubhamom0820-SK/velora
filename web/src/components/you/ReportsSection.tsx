"use client";

import { receivedDay } from "@/components/gifts/ReceivedGifts";
import { t } from "@/i18n/t";
import { useFiledReports } from "@/lib/queries/safety";

import { PersonRow } from "./PersonRow";
import { PagedList, YouSection } from "./YouSection";

/**
 * The reports you filed (T-9.8, D-911): whom, why and when. Never a status
 * and never a time to an answer: what moderation did isn't said, and the 24
 * hours wait on T-9.5 (P-761). The rows open nothing: a report is no reason
 * to visit, and across a block there is nothing to see.
 */
export function ReportsSection() {
  const reports = useFiledReports();
  return (
    <YouSection title={t("you.reports.title")} body={t("you.reports.body")}>
      <PagedList
        query={reports}
        empty={t("you.reports.empty")}
        failed={t("you.reports.failed")}
        row={(item) => (
          <PersonRow
            key={item.id}
            person={item.reported}
            detail={t("you.reports.row", {
              reason: t(`profile.reason.${item.reason}`),
              date: receivedDay.format(new Date(item.created_at)),
            })}
          />
        )}
      />
    </YouSection>
  );
}
