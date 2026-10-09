"use client";

import { Button } from "@/components/ui/Button";
import { buttonClasses } from "@/components/ui/buttonClasses";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { useDataExport, useRequestExport } from "@/lib/queries/account";

import { YouSection } from "./YouSection";

/** When the link stops working, in the reader's own time zone. */
const untilTime = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "short",
});

/**
 * A copy of your data (T-9.6's `POST`/`GET /me/export`, D-502): ask for one,
 * wait while it's made, then a link that works for 24 hours, until the
 * `expires_at` the API gives. Failed or expired, ask again; five a day.
 */
export function DataExportSection() {
  const current = useDataExport();
  const request = useRequestExport();

  const asking = (label: string) => (
    <div>
      <Button
        variant="ghost"
        size="sm"
        loading={request.isPending}
        onClick={() => request.mutate()}
      >
        {label}
      </Button>
    </div>
  );

  let body;
  if (current.isPending) body = <Skeleton className="w-1/2" />;
  else if (current.isError)
    body = (
      <ErrorState
        title={t("settings.export.loadFailed")}
        onRetry={() => void current.refetch()}
      />
    );
  else {
    const made = current.data;
    if (made === null || made.status === "expired")
      body = asking(
        made === null
          ? t("settings.export.ask")
          : t("settings.export.askAgain"),
      );
    else if (made.status === "pending")
      body = (
        <p role="status" className="text-body text-mute">
          {t("settings.export.pending")}
        </p>
      );
    else if (made.status === "failed")
      body = (
        <>
          <p className="text-body text-accent">{t("settings.export.failed")}</p>
          {asking(t("settings.export.askAgain"))}
        </>
      );
    else
      body = (
        <>
          {made.url && (
            <div>
              {/* A plain link: the signed file is on the bucket, never a
                  route Next should prefetch. */}
              <a
                href={made.url}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonClasses({ size: "sm" })}
              >
                {t("settings.export.ready")}
              </a>
            </div>
          )}
          {made.expires_at && (
            <p className="text-small text-mute">
              {t("settings.export.until", {
                time: untilTime.format(new Date(made.expires_at)),
              })}
            </p>
          )}
        </>
      );
  }

  const refused =
    request.error instanceof ApiError && request.error.code === "RATE_LIMITED"
      ? t("settings.export.tooMany")
      : request.isError
        ? t("settings.export.failed")
        : null;

  return (
    <YouSection
      title={t("settings.export.title")}
      body={t("settings.export.body")}
    >
      {body}
      {refused && (
        <p role="alert" className="text-small text-accent">
          {refused}
        </p>
      )}
    </YouSection>
  );
}
