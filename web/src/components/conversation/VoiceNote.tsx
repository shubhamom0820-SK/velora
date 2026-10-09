"use client";

import { Lock, Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { creditsText } from "@/lib/credits";
import { cx } from "@/lib/cx";
import {
  useUnlockVoice,
  useVoiceMedia,
  type Message,
} from "@/lib/queries/messages";

import { duration } from "./format";

/** How many bars the waveform draws. */
const BARS = 28;

/** A bar's height, as classes: no inline style for the CSP to weigh (P-41). */
const HEIGHTS = [
  "h-[28%]",
  "h-[40%]",
  "h-[52%]",
  "h-[64%]",
  "h-[76%]",
  "h-[88%]",
  "h-full",
] as const;

/**
 * Decorative bars, the same for a message every time (from its id): real
 * peaks would mean decoding audio he hasn't paid to hear.
 */
export function barsOf(id: string): (typeof HEIGHTS)[number][] {
  let seed = 0;
  for (const char of id) seed = (seed * 31 + char.charCodeAt(0)) >>> 0;
  return Array.from({ length: BARS }, () => {
    seed = (seed * 1103515245 + 12345) >>> 0;
    return HEIGHTS[(seed >>> 16) % HEIGHTS.length] ?? "h-full";
  });
}

type VoiceNoteProps = {
  message: Message;
  /**
   * What unlocking costs, from `/prices` (`voice_unlock`): a number once it
   * has loaded, undefined while it loads. Only a locked note reads it, and a
   * note is locked only for him (T-7.9), so she is never shown a price.
   */
  unlockPrice: number | undefined;
};

/**
 * A voice note (08-DESIGN §8): a 32 px `--accent` play button, the bars
 * (`--ink` played, `--line-strong` the rest) and its length, measured by the
 * server (D-620). Locked for him until he unlocks it at the price shown (P-56,
 * D-600, D-621); the file is reached only by a link signed for 10 minutes,
 * asked for as the note is drawn, so a tap plays at once.
 */
export function VoiceNote({ message, unlockPrice }: VoiceNoteProps) {
  const toast = useToast();
  const unlock = useUnlockVoice();
  const link = useVoiceMedia(message.id, !message.locked);
  const audio = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [played, setPlayed] = useState(0);
  const [playAfterUnlock, setPlayAfterUnlock] = useState(false);
  const length = message.duration_s ?? 0;
  const url = link.data?.url;

  useEffect(() => {
    const element = audio.current;
    if (!playAfterUnlock || !url || !element) return;
    setPlayAfterUnlock(false);
    // A browser may want a second tap after the wait: the play button stays.
    element.play().catch(() => {});
  }, [playAfterUnlock, url]);

  async function onUnlock() {
    if (unlockPrice === undefined) return;
    try {
      await unlock.mutateAsync({
        threadId: message.thread_id,
        messageId: message.id,
        shown_price: unlockPrice,
      });
      setPlayAfterUnlock(true);
    } catch (error) {
      if (!(error instanceof ApiError)) {
        toast.show({
          message: t("conversation.voice.unlockFailed"),
          tone: "error",
        });
      } else if (error.code === "PRICE_CHANGED") {
        toast.show({
          message: t("conversation.priceChanged", {
            velas: creditsText(Number(error.details?.price)),
          }),
          tone: "error",
        });
      } else if (error.code !== "INSUFFICIENT_CREDITS") {
        // Out of Velas opens the store sheet instead (QueryProvider).
        toast.show({
          message: t("conversation.voice.unlockFailed"),
          tone: "error",
        });
      }
    }
  }

  function toggle() {
    const element = audio.current;
    if (!element || !url) {
      if (link.isError) void link.refetch();
      return;
    }
    if (element.paused) {
      element.play().catch(() =>
        toast.show({
          message: t("conversation.voice.playFailed"),
          tone: "error",
        }),
      );
    } else {
      element.pause();
    }
  }

  const bars = barsOf(message.id);
  const label = t("conversation.voice.label", { duration: duration(length) });

  if (message.locked) {
    return (
      <div className="flex flex-col gap-2" aria-label={label} role="group">
        <span className="text-small text-mute flex items-center gap-2">
          <Icon icon={Lock} size={14} />
          {label}
        </span>
        <Button
          size="sm"
          loading={unlock.isPending}
          disabled={unlockPrice === undefined}
          aria-label={
            unlockPrice === undefined
              ? undefined
              : t("conversation.voice.unlockLabel", {
                  velas: creditsText(unlockPrice),
                })
          }
          onClick={() => void onUnlock()}
        >
          {unlockPrice === undefined
            ? t("conversation.voice.unlock", { velas: "…" })
            : t("conversation.voice.unlock", {
                velas: creditsText(unlockPrice),
              })}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2.5" role="group" aria-label={label}>
      <button
        type="button"
        onClick={toggle}
        aria-label={t(
          playing ? "conversation.voice.pause" : "conversation.voice.play",
        )}
        className="bg-accent text-on-accent rounded-pill focus-visible:outline-accent relative flex size-8 shrink-0 items-center justify-center before:absolute before:-inset-1.5 focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        <Icon
          icon={playing ? Pause : Play}
          size={16}
          className="fill-current"
        />
      </button>
      <span aria-hidden className="flex h-7 items-center gap-0.5">
        {bars.map((height, index) => (
          <span
            key={index}
            data-played={index / BARS < played || undefined}
            className={cx(
              "rounded-pill w-0.5",
              height,
              index / BARS < played ? "bg-ink" : "bg-line-strong",
            )}
          />
        ))}
      </span>
      <span className="text-micro text-mute tabular-nums">
        {duration(length)}
      </span>
      {url && (
        <audio
          ref={audio}
          src={url}
          preload="metadata"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => {
            setPlaying(false);
            setPlayed(0);
          }}
          onTimeUpdate={(event) => {
            const element = event.currentTarget;
            const total = Number.isFinite(element.duration)
              ? element.duration
              : length;
            setPlayed(total > 0 ? element.currentTime / total : 0);
          }}
          onError={() => {
            // The link may have run out: ask for a fresh one.
            void link.refetch();
          }}
        />
      )}
    </div>
  );
}
