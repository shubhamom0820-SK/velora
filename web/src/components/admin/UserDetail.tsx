"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { deltaText } from "@/lib/credits";
import { useAdminUser, type AdminUserDetail } from "@/lib/queries/admin";
import { useMe } from "@/lib/queries/me";

import { CreditsForm } from "./CreditsForm";
import { PhotoCard } from "./PhotoCard";
import { StatusActions } from "./StatusActions";
import { entryTime } from "./time";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-title-2">{title}</h2>
      {children}
    </section>
  );
}

function NoneYet() {
  return <p className="text-small text-mute">{t("admin.user.noneYet")}</p>;
}

function Summary({
  detail,
  isAdmin,
}: {
  detail: AdminUserDetail;
  isAdmin: boolean;
}) {
  const { user } = detail;
  return (
    <section className="border-line bg-surface rounded-card flex flex-col gap-2 border p-4">
      <h1 className="text-title-1">
        {user.first_name ?? t("admin.users.unnamed")}
        {user.username && <span className="text-mute"> @{user.username}</span>}
      </h1>
      <div className="flex flex-wrap gap-2">
        <Badge tone={user.status === "active" ? "soft" : "ink"}>
          {t(`admin.status.${user.status}`)}
        </Badge>
        {user.erased && <Badge tone="soft">{t("admin.users.erased")}</Badge>}
        {detail.is_verified && (
          <Badge tone="soft">{t("ui.selfieMatched")}</Badge>
        )}
        {detail.ban && (
          <Badge tone="ink">
            {t("admin.user.banned", { reason: detail.ban.reason ?? "?" })}
          </Badge>
        )}
      </div>
      <p className="text-small text-mute">
        {[user.city, user.age, user.gender, user.role, user.onboarding_step]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {detail.phone && (
        <p className="text-body">
          {t("admin.user.phone")}: {detail.phone}
          {detail.phone_masked && (
            <span className="text-small text-mute block">
              {t("admin.user.phoneMasked")}
            </span>
          )}
        </p>
      )}
      {user.gender === "male" && (
        <p className="text-body">
          {t("admin.user.balance", { count: detail.balance })}
        </p>
      )}
      <StatusActions detail={detail} isAdmin={isAdmin} />
      {isAdmin && user.gender === "male" && !user.erased && (
        <CreditsForm userId={user.id} />
      )}
    </section>
  );
}

/**
 * One account for staff (T-9.5): who they are, the number as their role may
 * see it (D-927), their photos, fraud signals, reports both ways, ledger and
 * chats, and the actions their status allows. Asked once: every read is
 * audited, so "Refresh" asks again.
 */
export function UserDetail({ id }: { id: string }) {
  const detail = useAdminUser(id);
  const isAdmin = useMe().data?.role === "admin";

  if (detail.isError) {
    return (
      <ErrorState
        title={t("admin.failed")}
        onRetry={() => void detail.refetch()}
      />
    );
  }
  if (!detail.data) {
    return (
      <div aria-busy="true" className="flex flex-col gap-3">
        <Skeleton variant="card" />
        <Skeleton variant="card" />
      </div>
    );
  }
  const data = detail.data;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          loading={detail.isFetching}
          onClick={() => void detail.refetch()}
        >
          {t("admin.refresh")}
        </Button>
      </div>
      <Summary detail={data} isAdmin={isAdmin} />
      <Section title={t("admin.user.photos")}>
        {data.photos.length === 0 ? (
          <NoneYet />
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {data.photos.map((photo) => (
              <PhotoCard key={photo.id} photo={photo} />
            ))}
          </div>
        )}
      </Section>
      <Section title={t("admin.user.reportsAbout")}>
        {data.reports_about.length === 0 ? (
          <NoneYet />
        ) : (
          <ul className="flex flex-col gap-1">
            {data.reports_about.map((report) => (
              <li key={report.id} className="text-small">
                {t(`admin.reports.reasons.${report.reason}`)} ·{" "}
                {t(`admin.status.${report.reporter.status}`)} · {report.status}
                {report.details && (
                  <span className="text-mute block">{report.details}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("admin.user.reportsBy")}>
        {data.reports_by.length === 0 ? (
          <NoneYet />
        ) : (
          <ul className="flex flex-col gap-1">
            {data.reports_by.map((report) => (
              <li key={report.id} className="text-small">
                <Link
                  href={`/admin/users/${report.reported.id}`}
                  className="underline"
                >
                  {report.reported.first_name ?? t("admin.users.unnamed")}
                </Link>{" "}
                · {t(`admin.reports.reasons.${report.reason}`)} ·{" "}
                {report.status}
              </li>
            ))}
          </ul>
        )}
      </Section>
      {data.fraud && (
        <Section
          title={t("admin.user.fraud", {
            score: data.fraud.score,
            band: data.fraud.band,
          })}
        >
          <ul className="flex flex-col gap-1">
            {data.fraud.events.map((event) => (
              <li
                key={`${event.signal}-${event.created_at}`}
                className="text-small"
              >
                {event.signal} · {event.weight} ·{" "}
                {entryTime.format(new Date(event.created_at))}
              </li>
            ))}
          </ul>
        </Section>
      )}
      <Section title={t("admin.user.ledger")}>
        {data.ledger.length === 0 ? (
          <NoneYet />
        ) : (
          <ul className="flex flex-col gap-1">
            {data.ledger.map((entry) => (
              <li
                key={entry.id}
                className="text-small flex justify-between gap-2"
              >
                <span>
                  {t(`wallet.reason.${entry.reason}`, { app: APP_NAME })} ·{" "}
                  {entryTime.format(new Date(entry.created_at))}
                </span>
                <span>{deltaText(entry.delta)}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title={t("admin.user.threads")}>
        {data.threads.length === 0 ? (
          <NoneYet />
        ) : (
          <ul className="flex flex-col gap-1">
            {data.threads.map((thread) => (
              <li key={thread.id} className="text-small">
                <Link
                  href={`/admin/threads/${thread.id}`}
                  className="underline"
                >
                  {thread.other.first_name ?? t("admin.users.unnamed")}
                </Link>{" "}
                · {thread.status} · {thread.message_count}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
