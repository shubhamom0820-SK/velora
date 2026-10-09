import { t } from "@/i18n/t";

const DAY_MS = 24 * 60 * 60 * 1000;

const clock = new Intl.DateTimeFormat("en-IN", {
  hour: "numeric",
  minute: "2-digit",
  hour12: true,
});
const day = new Intl.DateTimeFormat("en-IN", {
  weekday: "short",
  day: "numeric",
  month: "short",
});
const date = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "long",
});

/** "7:49 PM", in the reader's own time zone. */
export function clockTime(iso: string): string {
  return clock.format(new Date(iso)).toUpperCase();
}

/** "4 October". */
export function dayAndMonth(iso: string): string {
  return date.format(new Date(iso));
}

/** Midnight before `ms`, in the reader's time zone. */
function startOfDay(ms: number): number {
  const at = new Date(ms);
  at.setHours(0, 0, 0, 0);
  return at.getTime();
}

/** Whole days from `iso`'s day to `now`'s, in the reader's time zone. */
function daysBefore(iso: string, now: number): number {
  return Math.round((startOfDay(now) - startOfDay(Date.parse(iso))) / DAY_MS);
}

/** A day separator: "Today", "Yesterday", or "Mon, 6 Oct". */
export function dayLabel(iso: string, now: number): string {
  const days = daysBefore(iso, now);
  if (days === 0) return t("conversation.today");
  if (days === 1) return t("conversation.yesterday");
  return day.format(new Date(iso));
}

/** The calendar day a message falls on, to know where a separator goes. */
export function dayKey(iso: string): number {
  return startOfDay(Date.parse(iso));
}

/** "Knotted today", "Knotted yesterday", "Knotted 3 days ago". */
export function knottedAgo(iso: string, now: number): string {
  const days = Math.max(0, daysBefore(iso, now));
  if (days === 0) return t("conversation.knottedToday");
  if (days === 1) return t("conversation.knottedYesterday");
  return t("conversation.knottedDays", { days });
}

/** A voice note's length: "0:12", "1:00". */
export function duration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
