"use client";

import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

const HOUR_MS = 60 * 60 * 1000;
// Read again each minute: the hours shown move slowly.
const TICK_MS = 60 * 1000;

/**
 * A report's day (P-761's "within 24 hours"): the hours left before `dueAt`,
 * the API's own deadline, or how long past it, in the accent once overdue.
 */
export function SlaTimer({ dueAt }: { dueAt: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), TICK_MS);
    return () => clearInterval(timer);
  }, []);

  const left = new Date(dueAt).getTime() - now;
  const overdue = left < 0;
  // Whole hours: rounded up while there is time, so "due in 1 h" never means
  // it is already late; down once late, so "overdue by 6 h" is at least six.
  const hours = overdue
    ? Math.floor(-left / HOUR_MS)
    : Math.ceil(left / HOUR_MS);
  return (
    <span
      className={cx(
        "text-small",
        overdue ? "text-accent font-semibold" : "text-mute",
      )}
    >
      {overdue
        ? t("admin.reports.overdue", { hours })
        : t("admin.reports.due", { hours })}
    </span>
  );
}
