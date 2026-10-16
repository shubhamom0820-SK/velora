"use client";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { t, type MessageKey } from "@/i18n/t";
import { useAdminMetrics, type AdminMetrics } from "@/lib/queries/admin";

import { entryTime } from "./time";

const STATUSES = ["active", "paused", "frozen", "banned", "deleted"] as const;

const rupees = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

function money(paise: number): string {
  return t("admin.metrics.rupees", { amount: rupees.format(paise / 100) });
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-line bg-surface rounded-card flex flex-col gap-1 border p-4">
      <span className="text-small text-mute">{label}</span>
      <span className="text-title-2 text-ink">{value}</span>
    </div>
  );
}

function tiles(figures: AdminMetrics): [MessageKey, string][] {
  return [
    ["admin.metrics.reportsOpen", String(figures.reports_open)],
    [
      "admin.metrics.oldestReport",
      figures.oldest_open_report_at
        ? entryTime.format(new Date(figures.oldest_open_report_at))
        : t("admin.none"),
    ],
    ["admin.metrics.photosPending", String(figures.photos_pending)],
    ["admin.metrics.frozen", String(figures.frozen)],
    ["admin.metrics.claimsOpen", String(figures.claims_open)],
    ["admin.metrics.signups24h", String(figures.signups_24h)],
    ["admin.metrics.signups7d", String(figures.signups_7d)],
  ];
}

/**
 * The dashboard (D-926): counts for staff; money in for an admin only, which
 * the API sends as null to a moderator, so this shows nothing for it then.
 */
export function MetricTiles() {
  const metrics = useAdminMetrics();

  if (metrics.isError) {
    return (
      <ErrorState
        title={t("admin.failed")}
        onRetry={() => void metrics.refetch()}
      />
    );
  }
  if (!metrics.data) {
    return (
      <div aria-busy="true" className="grid grid-cols-2 gap-3">
        <Skeleton variant="card" />
        <Skeleton variant="card" />
      </div>
    );
  }
  const figures = metrics.data;
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-title-1">{t("admin.metrics.title")}</h1>
        <Button
          variant="ghost"
          size="sm"
          loading={metrics.isFetching}
          onClick={() => void metrics.refetch()}
        >
          {t("admin.refresh")}
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {tiles(figures).map(([label, value]) => (
          <Tile key={label} label={t(label)} value={value} />
        ))}
      </div>
      <h2 className="text-title-2">{t("admin.metrics.byStatus")}</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
        {STATUSES.map((status) => (
          <Tile
            key={status}
            label={t(`admin.status.${status}`)}
            value={String(figures.users_by_status[status] ?? 0)}
          />
        ))}
      </div>
      {figures.revenue && (
        <>
          <h2 className="text-title-2">{t("admin.metrics.revenue")}</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <Tile
              label={t("admin.metrics.revenue7d")}
              value={money(figures.revenue.last_7_days_paise)}
            />
            <Tile
              label={t("admin.metrics.revenue30d")}
              value={money(figures.revenue.last_30_days_paise)}
            />
            <Tile
              label={t("admin.metrics.revenueYear", {
                year: figures.revenue.financial_year,
              })}
              value={money(figures.revenue.financial_year_paise)}
            />
          </div>
        </>
      )}
    </section>
  );
}
