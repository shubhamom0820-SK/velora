"use client";

import { Mic, Send, Square, Trash2 } from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import { useNow } from "@/lib/ticker";
import {
  RecorderError,
  VOICE_MIN_MS,
  durationSeconds,
  startRecording,
  type Recorder,
  type Recording,
} from "@/lib/voice-recorder";

import { duration } from "./format";

/** Held this long, a press records until it is let go; shorter, it is a tap. */
export const HOLD_MS = 400;

type Phase = "idle" | "starting" | "recording" | "preview";

export type NoteKey = Parameters<typeof t>[0];

type MicButtonProps = {
  /** True while recording or previewing: the composer hides its text. */
  onActiveChange: (active: boolean) => void;
  onSend: (recording: Recording) => void;
  /** What to tell her (refused, too short, capped), or null: the composer shows it. */
  onNote: (note: NoteKey | null) => void;
};

const NOTES: Record<RecorderError["failure"], NoteKey> = {
  denied: "conversation.voice.denied",
  unsupported: "conversation.voice.unsupported",
  failed: "conversation.voice.failed",
};

/**
 * Her mic (T-7.11; voice notes are hers, D-010): hold to record and let go to
 * stop, or tap to start and tap again to stop. It stops itself at a minute
 * (`voice-recorder`), and nothing is sent until she has heard it back and
 * tapped send. Under a second, it is thrown away.
 */
export function MicButton({ onActiveChange, onSend, onNote }: MicButtonProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [startedAt, setStartedAt] = useState(0);
  const setNote = onNote;
  const [recording, setRecording] = useState<Recording | null>(null);
  const recorder = useRef<Recorder | null>(null);
  const pressedAt = useRef<number | null>(null);
  const stopWanted = useRef(false);

  useEffect(() => {
    onActiveChange(phase !== "idle");
  }, [phase, onActiveChange]);

  // Her recording, played back before she sends it (CSP: media-src blob:).
  const previewUrl = useMemo(
    () => (recording ? URL.createObjectURL(recording.blob) : null),
    [recording],
  );
  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  // Leaving the screen mid-recording lets go of the microphone.
  useEffect(() => () => recorder.current?.cancel(), []);

  async function finish(capped = false) {
    const active = recorder.current;
    if (!active) {
      stopWanted.current = true;
      return;
    }
    recorder.current = null;
    try {
      const made = await active.stop();
      if (made.durationMs < VOICE_MIN_MS) {
        setNote("conversation.voice.tooShort");
        setPhase("idle");
        return;
      }
      setNote(capped ? "conversation.voice.capped" : null);
      setRecording(made);
      setPhase("preview");
    } catch {
      setNote("conversation.voice.failed");
      setPhase("idle");
    }
  }

  async function begin() {
    setNote(null);
    setPhase("starting");
    stopWanted.current = false;
    try {
      recorder.current = await startRecording({
        onCapped: () => void finish(true),
      });
    } catch (error) {
      setNote(
        error instanceof RecorderError
          ? NOTES[error.failure]
          : "conversation.voice.failed",
      );
      setPhase("idle");
      return;
    }
    setStartedAt(Date.now());
    setPhase("recording");
    // Let go before the microphone was ready: stop as soon as it is.
    if (stopWanted.current) void finish();
  }

  function discard() {
    recorder.current?.cancel();
    recorder.current = null;
    setRecording(null);
    setNote(null);
    setPhase("idle");
  }

  function send() {
    if (!recording) return;
    onSend(recording);
    setRecording(null);
    setNote(null);
    setPhase("idle");
  }

  function onPointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (event.button !== 0) return;
    event.preventDefault();
    if (phase === "idle") {
      pressedAt.current = Date.now();
      void begin();
    } else if (phase === "recording" || phase === "starting") {
      pressedAt.current = null;
      void finish();
    }
  }

  function onPointerUp() {
    const at = pressedAt.current;
    pressedAt.current = null;
    if (at !== null && Date.now() - at >= HOLD_MS) void finish();
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    if (phase === "idle") void begin();
    else if (phase === "recording" || phase === "starting") void finish();
  }

  const recordingNow = phase === "recording" || phase === "starting";

  return (
    <div
      className={cx("flex items-center gap-2", phase !== "idle" && "flex-1")}
    >
      {phase === "preview" && recording && (
        <>
          <button
            type="button"
            onClick={discard}
            aria-label={t("conversation.voice.discard")}
            className="text-mute focus-visible:outline-accent rounded-pill relative p-2 focus-visible:outline-2"
          >
            <Icon icon={Trash2} size={20} />
          </button>
          {previewUrl && (
            <audio
              controls
              src={previewUrl}
              aria-label={t("conversation.voice.preview", {
                duration: duration(durationSeconds(recording.durationMs)),
              })}
              className="h-11 min-w-0 flex-1"
            />
          )}
          <button
            type="button"
            onClick={send}
            aria-label={t("conversation.voice.send")}
            className="bg-accent text-on-accent shadow-1 rounded-pill focus-visible:outline-accent flex size-11 shrink-0 items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            <Icon icon={Send} size={20} />
          </button>
        </>
      )}
      {recordingNow && (
        <>
          <button
            type="button"
            onClick={discard}
            aria-label={t("conversation.voice.discard")}
            className="text-mute focus-visible:outline-accent rounded-pill relative p-2 focus-visible:outline-2"
          >
            <Icon icon={Trash2} size={20} />
          </button>
          <Elapsed since={startedAt} running={phase === "recording"} />
        </>
      )}
      {phase !== "preview" && (
        <button
          type="button"
          onPointerDown={onPointerDown}
          onPointerUp={onPointerUp}
          onKeyDown={onKeyDown}
          onContextMenu={(event) => event.preventDefault()}
          aria-label={t(
            recordingNow
              ? "conversation.voice.stop"
              : "conversation.voice.record",
          )}
          aria-pressed={recordingNow}
          className={cx(
            "rounded-pill focus-visible:outline-accent flex size-11 shrink-0 touch-none items-center justify-center select-none focus-visible:outline-2 focus-visible:outline-offset-2",
            recordingNow
              ? "bg-accent text-on-accent shadow-1"
              : "border-line text-ink border bg-surface",
          )}
        >
          <Icon icon={recordingNow ? Square : Mic} size={20} />
        </button>
      )}
    </div>
  );
}

/** "Recording, 0:12", moving with the shared ticker. */
function Elapsed({ since, running }: { since: number; running: boolean }) {
  const now = useNow();
  const seconds = running ? Math.max(0, (now - since) / 1000) : 0;
  return (
    <span className="text-small text-accent flex flex-1 items-center gap-2 tabular-nums">
      <span
        aria-hidden
        className="bg-accent rounded-pill size-2.5 motion-safe:animate-pulse"
      />
      {t("conversation.voice.recording", {
        time: duration(Math.floor(seconds)),
      })}
    </span>
  );
}
