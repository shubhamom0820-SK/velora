"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { t } from "@/i18n/t";
import {
  useAdminReports,
  useResolveReport,
  type AdminReport,
  type ReportAction,
} from "@/lib/queries/admin";
import { useMe } from "@/lib/queries/me";

import { AdminList } from "./AdminList";
import { ConfirmAction } from "./ConfirmAction";
import { SlaTimer } from "./SlaTimer";
import { entryTime } from "./time";

/** What staff may do with a report; a ban is an admin's alone (D-921). */
const ACTIONS: readonly ReportAction[] = ["none", "warn", "freeze", "ban"];

function name(person: AdminReport["reported"]): string {
  return person.first_name ?? person.username ?? t("admin.users.unnamed");
}

function ReportCard({ report }: { report: AdminReport }) {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<ReportAction | null>(null);
  const resolve = useResolveReport();
  const isAdmin = useMe().data?.role === "admin";
  const allowed = ACTIONS.filter((choice) => isAdmin || choice !== "ban");

  return (
    <article className="border-line bg-surface rounded-card flex flex-col gap-2 border p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-ui text-ink font-semibold">
          {t(`admin.reports.reasons.${report.reason}`)}
        </span>
        <SlaTimer dueAt={report.due_at} />
      </div>
      <Link
        href={`/admin/users/${report.reported.id}`}
        className="text-ui text-accent underline"
      >
        {t("admin.reports.about", { name: name(report.reported) })}
      </Link>
      <Link
        href={`/admin/users/${report.reporter.id}`}
        className="text-small text-mute"
      >
        {t("admin.reports.by", { name: name(report.reporter) })}
      </Link>
      {report.details && <p className="text-body text-ink">{report.details}</p>}
      <time dateTime={report.created_at} className="text-micro text-mute">
        {entryTime.format(new Date(report.created_at))}
      </time>
      <div className="flex flex-wrap gap-2">
        {report.thread_id && (
          <Link
            href={`/admin/threads/${report.thread_id}?report=${report.id}`}
            className="text-small text-accent underline"
          >
            {t("admin.reports.readChat")}
          </Link>
        )}
        <Button size="sm" onClick={() => setOpen(true)}>
          {t("admin.reports.resolve")}
        </Button>
      </div>
      <ConfirmAction
        open={open}
        onClose={() => setOpen(false)}
        title={t("admin.reports.resolveTitle")}
        confirmLabel={t("admin.reports.resolve")}
        variant={action === "ban" || action === "freeze" ? "danger" : "primary"}
        pending={resolve.isPending}
        error={resolve.error}
        ready={action !== null}
        onConfirm={(note) => {
          if (action === null) return;
          resolve.mutate(
            { id: report.id, action, note },
            { onSuccess: () => setOpen(false) },
          );
        }}
      >
        <div role="group" className="flex flex-wrap gap-2">
          {allowed.map((choice) => (
            <Chip
              key={choice}
              active={action === choice}
              onClick={() => setAction(choice)}
            >
              {t(`admin.reports.actions.${choice}`)}
            </Chip>
          ))}
        </div>
      </ConfirmAction>
    </article>
  );
}

/**
 * The report queue (T-9.5, D-921): open reports, oldest first, each with its
 * day (P-761), the person it is about, the chat if one is named, and a
 * resolution behind a confirmation.
 */
export function ReportQueue() {
  const reports = useAdminReports();
  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.reports.title")}</h1>
      <AdminList
        query={reports}
        empty={t("admin.reports.empty")}
        keyOf={(report) => report.id}
      >
        {(report) => <ReportCard report={report} />}
      </AdminList>
    </section>
  );
}
