/**
 * Recording a voice note (T-7.11): the web's only MediaRecorder, used by the
 * conversation's mic and by `/dev/voice`, where P-520's real recordings were
 * made, so what was measured there is what the app sends.
 *
 * The type is the first the browser records of WebM Opus, Ogg Opus and MP4
 * (Safari's), the three the API takes (D-620). The server measures the length
 * from the bytes and keeps that; `durationMs` here is the recorder's own clock,
 * from its `start` to its `stop`, sent as `duration_s` and only checked (1 to
 * 60). At 64 kbps a minute is about 480 kB, far under the API's 2 MB.
 */

/** In order of preference, as `MediaRecorder.isTypeSupported` is asked. */
export const VOICE_TYPES = [
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
  "audio/mp4",
] as const;

/** What the API signs an upload for: the type without its codecs. */
export type VoiceContentType = "audio/webm" | "audio/ogg" | "audio/mp4";

/** The cap (D-620): the recorder stops itself here. */
export const VOICE_MAX_MS = 60_000;
/** Shorter than a second is no voice note: the API takes 1 to 60 seconds. */
export const VOICE_MIN_MS = 1_000;
export const VOICE_BITS_PER_SECOND = 64_000;

export type Recording = {
  blob: Blob;
  contentType: VoiceContentType;
  /** The recorder's own length, `start` to `stop`, in milliseconds. */
  durationMs: number;
};

/**
 * Why recording couldn't start: no recorder or no type the API takes
 * (`unsupported`), the microphone refused (`denied`), or anything else.
 */
export type RecorderFailure = "unsupported" | "denied" | "failed";

export class RecorderError extends Error {
  readonly failure: RecorderFailure;

  constructor(failure: RecorderFailure) {
    super(`Recording failed: ${failure}.`);
    this.name = "RecorderError";
    this.failure = failure;
  }
}

/** The first of `VOICE_TYPES` this browser records, or null. */
export function pickVoiceType(
  supported: (type: string) => boolean,
): (typeof VOICE_TYPES)[number] | null {
  return VOICE_TYPES.find((type) => supported(type)) ?? null;
}

export function contentTypeOf(mimeType: string): VoiceContentType | null {
  const base = mimeType.split(";")[0]?.trim().toLowerCase();
  return base === "audio/webm" || base === "audio/ogg" || base === "audio/mp4"
    ? base
    : null;
}

/** A file's extension for `/dev/voice`'s saves, as the API's keys name them. */
export function extensionOf(type: VoiceContentType): string {
  return { "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a" }[type];
}

/** `duration_s` for the API: whole seconds, 1 to 60. */
export function durationSeconds(durationMs: number): number {
  return Math.min(60, Math.max(1, Math.round(durationMs / 1000)));
}

export type Recorder = {
  /** Stops, and resolves with the recording once the browser hands it over. */
  stop: () => Promise<Recording>;
  /** Stops and throws the recording away. */
  cancel: () => void;
};

type Options = {
  /** Called when the cap stopped it; `stop()` then resolves the recording. */
  onCapped?: () => void;
};

/**
 * Asks for the microphone and starts recording. Rejects with `RecorderError`.
 * The microphone is released when it stops, however it stops.
 */
export async function startRecording({
  onCapped,
}: Options = {}): Promise<Recorder> {
  if (
    typeof MediaRecorder === "undefined" ||
    !navigator.mediaDevices?.getUserMedia
  ) {
    throw new RecorderError("unsupported");
  }
  const mimeType = pickVoiceType((type) => MediaRecorder.isTypeSupported(type));
  if (mimeType === null) throw new RecorderError("unsupported");

  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (error) {
    const name = error instanceof DOMException ? error.name : "";
    throw new RecorderError(
      name === "NotAllowedError" || name === "SecurityError"
        ? "denied"
        : "failed",
    );
  }

  let recorder: MediaRecorder;
  try {
    recorder = new MediaRecorder(stream, {
      mimeType,
      audioBitsPerSecond: VOICE_BITS_PER_SECOND,
    });
  } catch {
    stream.getTracks().forEach((track) => track.stop());
    throw new RecorderError("failed");
  }

  const chunks: Blob[] = [];
  let startedAt: number | null = null;
  let cancelled = false;
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  recorder.onstart = () => {
    startedAt = performance.now();
  };
  const stopped = new Promise<Recording>((resolve, reject) => {
    recorder.onstop = () => {
      const durationMs = startedAt === null ? 0 : performance.now() - startedAt;
      stream.getTracks().forEach((track) => track.stop());
      // The type the browser actually wrote, which may name its codecs.
      const contentType =
        contentTypeOf(recorder.mimeType || mimeType) ??
        (contentTypeOf(mimeType) as VoiceContentType);
      if (cancelled) {
        reject(new RecorderError("failed"));
        return;
      }
      resolve({
        blob: new Blob(chunks, { type: contentType }),
        contentType,
        durationMs,
      });
    };
    recorder.onerror = () => {
      stream.getTracks().forEach((track) => track.stop());
      reject(new RecorderError("failed"));
    };
  });
  // Nobody may wait on a cancelled recording; its rejection is expected.
  stopped.catch(() => {});

  const cap = setTimeout(() => {
    if (recorder.state === "recording") {
      recorder.stop();
      onCapped?.();
    }
  }, VOICE_MAX_MS);

  recorder.start();

  return {
    stop: () => {
      clearTimeout(cap);
      if (recorder.state === "recording") recorder.stop();
      return stopped;
    },
    cancel: () => {
      clearTimeout(cap);
      cancelled = true;
      if (recorder.state === "recording") recorder.stop();
      else stream.getTracks().forEach((track) => track.stop());
    },
  };
}
