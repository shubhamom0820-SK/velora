"use client";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import { useNow } from "@/lib/ticker";

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
/** Under this, the pill fills `--accent` (08-DESIGN §8: "under ten minutes"). */
const URGENT_MS = 10 * MINUTE_MS;

type Phase = "extended" | "running" | "urgent" | "out";

const TONES: Record<Phase, string> = {
  extended: "bg-surface-2 text-ink",
  running: "bg-accent-soft text-accent",
  urgent: "bg-accent text-on-accent",
  out: "bg-surface-2 text-mute",
};

/** What the pill says `leftMs` before the end, and how it looks. */
export function countdownOf(leftMs: number): { phase: Phase; text: string } {
  if (leftMs <= 0) return { phase: "out", text: t("ui.countdown.out") };
  if (leftMs > HOUR_MS) {
    // More than the hour: an Extended Thread, in whole hours ("22h left").
    const hours = Math.floor(leftMs / HOUR_MS);
    return { phase: "extended", text: t("ui.countdown.hours", { hours }) };
  }
  // Rounded up, so it never says "0m" while time is left, nor runs out early.
  const minutes = Math.ceil(leftMs / MINUTE_MS);
  return {
    phase: leftMs < URGENT_MS ? "urgent" : "running",
    text:
      minutes === 60
        ? t("ui.countdown.hours", { hours: 1 })
        : t("ui.countdown.minutes", { minutes }),
  };
}

/**
 * A Thread's time left (08-DESIGN §4, §8): "41m left" on `--accent-soft`,
 * "22h left" on `--surface-2` for an Extended one, filled `--accent` under ten
 * minutes, and "Ran out". Every Countdown reads one shared ticker (`useNow`).
 * His alone: a woman is never shown one (D-097, D-554, P-460), which is the
 * caller's to decide.
 */
export function Countdown({ expiresAt }: { expiresAt: string }) {
  const now = useNow();
  const { phase, text } = countdownOf(Date.parse(expiresAt) - now);
  return (
    <span
      data-phase={phase}
      className={cx(
        "rounded-pill text-micro inline-flex shrink-0 items-center px-2 py-0.5 font-semibold tabular-nums",
        TONES[phase],
      )}
    >
      {text}
    </span>
  );
}
