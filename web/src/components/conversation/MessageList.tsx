"use client";

import { Check, CheckCheck } from "lucide-react";
import { memo, type ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import type { Message } from "@/lib/queries/messages";

import { clockTime, dayAndMonth, dayKey, dayLabel } from "./format";
import { VoiceNote } from "./VoiceNote";

/**
 * A message of mine not yet stored: shown at once under its `client_msg_id`,
 * then replaced by the API's copy (the same id), or kept with Retry.
 */
export type Pending = {
  client_msg_id: string;
  created_at: string;
  state: "sending" | "failed";
} & (
  | { kind: "text"; body: string }
  | { kind: "voice"; duration_s: number; progress: number }
);

type MessageListProps = {
  /** Oldest first. */
  messages: Message[];
  /** Mine, not yet stored, oldest first. */
  pending: Pending[];
  /**
   * His expired Thread's moment (D-097): where "The hour ran out" goes, and
   * her messages after it marked new. Null for her, always (P-460), and for a
   * live Thread, a Knot or a private message.
   */
  ranOutAt: string | null;
  /** When the Knot was tied, for its divider; null if it isn't one. */
  knottedAt: string | null;
  /** The other person's name, for "… is typing". */
  theirName: string;
  typing: boolean;
  /** What his unlock costs, for his locked voice notes. */
  unlockPrice: number | undefined;
  /** The time the list was drawn, for "Today" and "Yesterday". */
  now: number;
  onRetry: (pending: Pending) => void;
};

function Divider({
  children,
  accent,
}: {
  children: ReactNode;
  accent?: boolean;
}) {
  return (
    <li
      role="separator"
      className={cx(
        "text-micro flex items-center gap-3 py-2 font-semibold",
        accent ? "text-accent uppercase" : "text-mute",
      )}
    >
      <span
        aria-hidden
        className={cx("h-px flex-1", accent ? "bg-accent" : "bg-line")}
      />
      {children}
      <span
        aria-hidden
        className={cx("h-px flex-1", accent ? "bg-accent" : "bg-line")}
      />
    </li>
  );
}

/** Whether a message comes after a moment (equal counts as before). */
const after = (iso: string, moment: string) =>
  Date.parse(iso) > Date.parse(moment);

/**
 * The bubbles (08-DESIGN §8, `--corner-bubble`, the small corner toward the
 * sender): theirs `--surface` with a `--line` border, mine `--ink`. Day
 * separators; "The hour ran out" and the Knot's dividers; "Seen" or "Not seen
 * yet" under my last message; the typing dots. Their text is React's to
 * escape, never set as HTML.
 */
export const MessageList = memo(function MessageList({
  messages,
  pending,
  ranOutAt,
  knottedAt,
  theirName,
  typing,
  unlockPrice,
  now,
  onRetry,
}: MessageListProps) {
  const stored = new Set(messages.map((message) => message.client_msg_id));
  const waiting = pending.filter((item) => !stored.has(item.client_msg_id));
  const lastMine = [...messages].reverse().find((message) => message.mine);
  const items: ReactNode[] = [];
  let lastDay: number | null = null;
  let ranOutShown = false;
  let tiedShown = false;

  function separators(at: string) {
    if (ranOutAt && !ranOutShown && after(at, ranOutAt)) {
      ranOutShown = true;
      items.push(
        <Divider key="ran-out">{t("conversation.ranOutDivider")}</Divider>,
      );
    }
    if (knottedAt && !tiedShown && after(at, knottedAt)) {
      tiedShown = true;
      items.push(
        <Divider key="tied" accent>
          {t("conversation.tiedDivider", { date: dayAndMonth(knottedAt) })}
        </Divider>,
      );
    }
    const key = dayKey(at);
    if (key !== lastDay) {
      lastDay = key;
      items.push(<Divider key={`day-${key}`}>{dayLabel(at, now)}</Divider>);
    }
  }

  for (const message of messages) {
    separators(message.created_at);
    if (message.kind === "system") {
      items.push(
        <li key={message.id} className="text-micro text-mute py-1 text-center">
          {message.body}
        </li>,
      );
      continue;
    }
    const fresh =
      ranOutAt !== null && !message.mine && after(message.created_at, ranOutAt);
    items.push(
      <li
        key={message.id}
        className={cx(
          "flex flex-col gap-1",
          message.mine ? "items-end" : "items-start",
        )}
      >
        {fresh && (
          <span className="text-micro text-accent font-semibold">
            {t("conversation.newAt", { time: clockTime(message.created_at) })}
          </span>
        )}
        <Bubble mine={message.mine} fresh={fresh}>
          {message.kind === "voice" ? (
            <VoiceNote message={message} unlockPrice={unlockPrice} />
          ) : (
            <p className="whitespace-pre-wrap break-words">{message.body}</p>
          )}
        </Bubble>
        {message.masked && (
          <span className="text-micro text-mute max-w-[80%]">
            {t("conversation.masked")}
          </span>
        )}
        {message === lastMine && waiting.length === 0 && (
          <span className="text-micro text-mute flex items-center gap-1">
            <Icon icon={message.read_at ? CheckCheck : Check} size={14} />
            {message.read_at
              ? t("conversation.seen", { time: clockTime(message.read_at) })
              : t("conversation.notSeen")}
          </span>
        )}
      </li>,
    );
  }

  for (const item of waiting) {
    separators(item.created_at);
    items.push(
      <li key={item.client_msg_id} className="flex flex-col items-end gap-1">
        <Bubble mine faded={item.state === "sending"}>
          {item.kind === "text" ? (
            <p className="whitespace-pre-wrap break-words">{item.body}</p>
          ) : (
            <span className="text-small">
              {item.state === "sending"
                ? t("conversation.voice.uploading", { percent: item.progress })
                : t("conversation.voice.label", {
                    duration: `0:${String(item.duration_s).padStart(2, "0")}`,
                  })}
            </span>
          )}
        </Bubble>
        {item.state === "sending" ? (
          <span className="text-micro text-mute">
            {t("conversation.sending")}
          </span>
        ) : (
          <span className="text-micro text-accent flex items-center gap-2">
            {t("conversation.notSent")}
            <button
              type="button"
              onClick={() => onRetry(item)}
              className="font-semibold underline focus-visible:outline-accent focus-visible:outline-2"
            >
              {t("conversation.retry")}
            </button>
          </span>
        )}
      </li>,
    );
  }

  // Ran out after the last message: the divider goes at the end.
  if (ranOutAt && !ranOutShown) {
    items.push(
      <Divider key="ran-out">{t("conversation.ranOutDivider")}</Divider>,
    );
  }
  if (knottedAt && !tiedShown) {
    items.push(
      <Divider key="tied" accent>
        {t("conversation.tiedDivider", { date: dayAndMonth(knottedAt) })}
      </Divider>,
    );
  }
  if (typing) {
    items.push(
      <li key="typing" className="flex flex-col items-start gap-1">
        <Bubble mine={false}>
          <span aria-hidden className="flex h-5 items-center gap-1">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="bg-mute rounded-pill size-1.5 motion-safe:animate-pulse"
              />
            ))}
          </span>
        </Bubble>
        <span className="text-micro text-mute">
          {t("conversation.typing", { name: theirName })}
        </span>
      </li>,
    );
  }

  return (
    <ol aria-label={t("conversation.messages")} className="flex flex-col gap-2">
      {items}
    </ol>
  );
});

function Bubble({
  mine,
  fresh = false,
  faded = false,
  children,
}: {
  mine: boolean;
  fresh?: boolean;
  faded?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        "text-body max-w-[80%] px-3.5 py-2.5",
        mine
          ? "bg-ink text-chrome-ink rounded-t-bubble rounded-bl-bubble rounded-br-[4px]"
          : "bg-surface text-ink border rounded-t-bubble rounded-br-bubble rounded-bl-[4px]",
        !mine && (fresh ? "border-accent" : "border-line"),
        faded && "opacity-60",
      )}
    >
      {children}
    </div>
  );
}
