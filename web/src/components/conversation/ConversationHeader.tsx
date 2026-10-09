"use client";

import { ArrowLeft, Link2 } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Avatar } from "@/components/ui/Avatar";
import { countdownOf } from "@/components/ui/Countdown";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { creditsCount, creditsText } from "@/lib/credits";
import { cx } from "@/lib/cx";
import type { ThreadView } from "@/lib/queries/threads";

import { clockTime, knottedAgo } from "./format";

const HOUR_MS = 60 * 60 * 1000;

type ConversationHeaderProps = {
  thread: ThreadView;
  /**
   * His Thread's expiry, by the clock: what drives the countdown, the bar and
   * "The hour ran out". Null for her whatever the API sends (P-460), and for a
   * Knot or a private message.
   */
  hisExpiry: string | null;
  now: number;
  /** Extend's price from `/prices`, when he may Extend now; else undefined. */
  extendPrice: number | undefined;
  extending: boolean;
  onExtend: () => void;
  menu: ReactNode;
};

/**
 * The conversation's header (08-DESIGN §8), on `--chrome` under the shell's:
 * back, the other person, then what this Thread is. His: "41m left · her reply
 * restarts the hour" (the time in `--chrome-accent`) and "Extend 24h · 10"; once
 * it ran out, "The hour ran out · 7:52 PM". A Knot: "Knotted 3 days ago". Hers:
 * "Online now" or nothing, never a countdown, a price or an expiry (D-097).
 * Beneath it the thread's bar: the part of the hour left, his alone; full on a
 * Knot; `--chrome-line` alone otherwise.
 */
export function ConversationHeader({
  thread,
  hisExpiry,
  now,
  extendPrice,
  extending,
  onExtend,
  menu,
}: ConversationHeaderProps) {
  const other = thread.other;
  const name = other.deleted
    ? t("conversation.deletedAccount")
    : (other.first_name ?? "");
  const knotted = thread.status === "knotted" && thread.knotted_at !== null;
  const left = hisExpiry === null ? null : Date.parse(hisExpiry) - now;
  const online = other.is_online ? t("conversation.online") : null;

  let status: ReactNode = online;
  if (knotted) {
    status = [knottedAgo(thread.knotted_at ?? "", now), online]
      .filter(Boolean)
      .join(" · ");
  } else if (hisExpiry !== null && left !== null && left > 0) {
    status = (
      <>
        <span className="text-chrome-accent tabular-nums">
          {countdownOf(left).text}
        </span>
        {` · ${t("conversation.restarts")}`}
      </>
    );
  } else if (hisExpiry !== null) {
    status = t("conversation.ranOutAt", { time: clockTime(hisExpiry) });
  }

  const share = knotted
    ? 1
    : left === null
      ? 0
      : Math.min(1, Math.max(0, left / HOUR_MS));

  return (
    <div className="sticky top-(--shell-header-height) z-[5]">
      <div className="bg-chrome flex items-center gap-3 px-(--shell-gutter) py-2.5">
        <Link
          href="/chats"
          aria-label={t("conversation.back")}
          className="text-chrome-ink focus-visible:outline-accent rounded-pill relative -ml-1 p-1 before:absolute before:-inset-1.5 focus-visible:outline-2"
        >
          <Icon icon={ArrowLeft} size={22} />
        </Link>
        <span
          className={cx(
            "rounded-pill flex shrink-0",
            knotted && "ring-chrome-accent ring-2",
          )}
        >
          <Avatar
            name={name}
            src={other.main_photo_url ?? undefined}
            size={40}
            online={other.is_online}
            verified={other.shows_badge}
          />
        </span>
        <div className="flex min-w-0 flex-1 flex-col">
          <h1 className="text-ui text-chrome-ink flex items-center gap-1.5 truncate font-semibold">
            <span className="truncate">{name}</span>
            {knotted && (
              <Icon
                icon={Link2}
                size={14}
                label={t("chats.knot")}
                className="text-chrome-accent shrink-0"
              />
            )}
          </h1>
          {status && (
            <p className="text-micro text-chrome-mute truncate">{status}</p>
          )}
        </div>
        {extendPrice !== undefined && (
          <button
            type="button"
            onClick={onExtend}
            disabled={extending}
            aria-busy={extending || undefined}
            aria-label={t("conversation.extendLabel", {
              velas: creditsText(extendPrice),
            })}
            className="border-chrome-accent text-chrome-ink text-micro rounded-pill focus-visible:outline-accent relative shrink-0 border px-3 py-1.5 font-semibold before:absolute before:-inset-y-2 focus-visible:outline-2 disabled:opacity-60"
          >
            {t("conversation.extend", { count: creditsCount(extendPrice) })}
          </button>
        )}
        {menu}
      </div>
      <div
        aria-hidden
        data-testid="thread-bar"
        data-share={share}
        className="bg-chrome-line h-[3px]"
      >
        {share > 0 && (
          <div
            className="bg-chrome-accent h-full transition-[width] duration-1000"
            // Drawn only once the Thread has loaded, on the client: React sets
            // it through the CSSOM, which the CSP never weighs (P-41).
            style={{ width: `${share * 100}%` }}
          />
        )}
      </div>
    </div>
  );
}
