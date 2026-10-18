"use client";

import { Gift, Send } from "lucide-react";
import { useCallback, useState, type KeyboardEvent } from "react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { creditsText } from "@/lib/credits";
import { cx } from "@/lib/cx";
import { MESSAGE_MAX } from "@/lib/queries/messages";
import type { Recording } from "@/lib/voice-recorder";

import { MicButton, type NoteKey } from "./MicButton";

type ComposerProps = {
  draft: string;
  onDraftChange: (draft: string) => void;
  onSend: (text: string) => void;
  /** Her mic (D-010): a voice note is hers to send, never his. */
  canRecord: boolean;
  onSendVoice: (recording: Recording) => void;
  /**
   * What his next message costs, `send_price` (D-870), shown before he sends
   * and sent back as `shown_price` (P-56). Always 0 for her.
   */
  price: number;
  /** A private message: every one of his costs `price`. */
  privateMessage: boolean;
  /** What to tell them above the input: a refusal, a mic's note. */
  note: string | null;
  onNote: (note: string | null) => void;
  /** Called as they type something, for the other person's dots (T-7.12). */
  onTyping?: () => void;
  /**
   * His gift button (08-DESIGN §8, T-7.12): given only where the Thread says
   * a gift is taken (`can_gift`, D-880), never decided from a gender here.
   */
  gift?: { name: string; onOpen: () => void };
};

/**
 * The composer (08-DESIGN §8): the input at 16 px (`input`, so iOS doesn't
 * zoom) with `--corner-input`, a 44 px filled `--accent` send button and, for
 * her, a 44 px outlined mic. Enter sends; Shift+Enter is a new line; Enter
 * while an input method is composing (Hindi, say) never sends. When his next
 * message costs something, the line above says so and the button's name
 * carries the price.
 */
export function Composer({
  draft,
  onDraftChange,
  onSend,
  canRecord,
  onSendVoice,
  price,
  privateMessage,
  note,
  onNote,
  onTyping,
  gift,
}: ComposerProps) {
  const [recording, setRecording] = useState(false);
  const text = draft.trim();
  const priced = price > 0;
  const onMicNote = useCallback(
    (key: NoteKey | null) => onNote(key === null ? null : t(key)),
    [onNote],
  );

  function send() {
    if (text === "") return;
    onSend(text);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return;
    if (event.nativeEvent.isComposing) return;
    event.preventDefault();
    send();
  }

  return (
    <div className="bg-bg border-line flex flex-col gap-2 border-t px-(--shell-gutter) py-3">
      {note && (
        <p role="status" className="text-small text-accent">
          {note}
        </p>
      )}
      {priced && !recording && (
        <p className="text-micro text-mute">
          {t(
            privateMessage ? "conversation.priceDm" : "conversation.priceOne",
            {
              velas: creditsText(price),
            },
          )}
        </p>
      )}
      <div className="flex items-end gap-2">
        {!recording && (
          <>
            <textarea
              rows={1}
              value={draft}
              maxLength={MESSAGE_MAX}
              onChange={(event) => {
                onDraftChange(event.target.value);
                if (event.target.value.trim() !== "") onTyping?.();
              }}
              onKeyDown={onKeyDown}
              placeholder={t("conversation.placeholder")}
              aria-label={t("conversation.placeholder")}
              className="rounded-input border-line bg-surface text-input text-ink placeholder:text-mute focus-visible:border-accent max-h-32 min-h-11 min-w-0 flex-1 resize-none border px-3.5 py-2.5 [field-sizing:content]"
            />
            <button
              type="button"
              onClick={send}
              disabled={text === ""}
              aria-label={
                priced
                  ? t("conversation.sendPriced", { velas: creditsText(price) })
                  : t("conversation.send")
              }
              className={cx(
                "rounded-pill focus-visible:outline-accent flex size-11 shrink-0 items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2",
                "bg-accent text-on-accent shadow-1 disabled:bg-surface-2 disabled:text-mute disabled:shadow-none",
              )}
            >
              <Icon icon={Send} size={20} />
            </button>
          </>
        )}
        {gift && !recording && (
          <button
            type="button"
            onClick={gift.onOpen}
            aria-label={t("conversation.gift", { name: gift.name })}
            className="rounded-pill border-line text-ink focus-visible:outline-accent flex size-11 shrink-0 items-center justify-center border focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            <Icon icon={Gift} size={20} />
          </button>
        )}
        {canRecord && (
          <MicButton
            onActiveChange={setRecording}
            onSend={onSendVoice}
            onNote={onMicNote}
          />
        )}
      </div>
    </div>
  );
}
