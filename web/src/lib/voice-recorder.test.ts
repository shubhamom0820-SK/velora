import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  contentTypeOf,
  durationSeconds,
  pickVoiceType,
  RecorderError,
  startRecording,
  VOICE_TYPES,
} from "./voice-recorder";

/** A browser's MediaRecorder, as far as the recorder uses one. */
class FakeMediaRecorder {
  static supported: string[] = [];
  static last: FakeMediaRecorder | null = null;
  static isTypeSupported(type: string) {
    return FakeMediaRecorder.supported.includes(type);
  }
  state: "inactive" | "recording" = "inactive";
  mimeType: string;
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstart: (() => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(
    readonly stream: unknown,
    readonly options: { mimeType: string; audioBitsPerSecond: number },
  ) {
    this.mimeType = options.mimeType;
    FakeMediaRecorder.last = this;
  }
  start() {
    this.state = "recording";
    this.onstart?.();
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({
      data: new Blob(["opus"], { type: this.mimeType }),
    });
    this.onstop?.();
  }
}

const track = { stop: vi.fn() };
const stream = { getTracks: () => [track] };
let clock = 0;

function microphone(getUserMedia: () => Promise<unknown>) {
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn(getUserMedia) },
    configurable: true,
  });
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  clock = 1000;
  vi.spyOn(performance, "now").mockImplementation(() => clock);
  FakeMediaRecorder.supported = [...VOICE_TYPES];
  FakeMediaRecorder.last = null;
  track.stop.mockClear();
  vi.stubGlobal("MediaRecorder", FakeMediaRecorder);
  microphone(() => Promise.resolve(stream));
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "mediaDevices");
});

describe("the type a recording is made in (D-620)", () => {
  it("prefers WebM Opus, then Ogg Opus, then MP4: the three the API takes", () => {
    expect(VOICE_TYPES).toEqual([
      "audio/webm;codecs=opus",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ]);
    expect(pickVoiceType(() => true)).toBe("audio/webm;codecs=opus");
    expect(pickVoiceType((type) => type.startsWith("audio/ogg"))).toBe(
      "audio/ogg;codecs=opus",
    );
    // Safari records MP4 alone.
    expect(pickVoiceType((type) => type === "audio/mp4")).toBe("audio/mp4");
    expect(pickVoiceType(() => false)).toBeNull();
  });

  it("names the upload by the type alone, never its codecs, and nothing else", () => {
    expect(contentTypeOf("audio/webm;codecs=opus")).toBe("audio/webm");
    expect(contentTypeOf("audio/ogg; codecs=opus")).toBe("audio/ogg");
    expect(contentTypeOf("audio/mp4")).toBe("audio/mp4");
    expect(contentTypeOf("video/webm")).toBeNull();
    expect(contentTypeOf("audio/wav")).toBeNull();
  });

  it("sends whole seconds, 1 to 60, as the API bounds duration_s", () => {
    expect(durationSeconds(400)).toBe(1);
    expect(durationSeconds(5_400)).toBe(5);
    expect(durationSeconds(5_600)).toBe(6);
    expect(durationSeconds(60_400)).toBe(60);
  });
});

describe("startRecording", () => {
  it("records in the first type the browser takes, at 64 kbps", async () => {
    FakeMediaRecorder.supported = ["audio/ogg;codecs=opus", "audio/mp4"];

    await startRecording();

    expect(FakeMediaRecorder.last?.options).toEqual({
      mimeType: "audio/ogg;codecs=opus",
      audioBitsPerSecond: 64_000,
    });
    expect(FakeMediaRecorder.last?.state).toBe("recording");
  });

  it("measures its own length from start to stop, and lets go of the microphone", async () => {
    const recorder = await startRecording();
    clock += 5_250;

    const recording = await recorder.stop();

    expect(recording.durationMs).toBe(5_250);
    expect(recording.contentType).toBe("audio/webm");
    expect(recording.blob.type).toBe("audio/webm");
    expect(recording.blob.size).toBeGreaterThan(0);
    expect(track.stop).toHaveBeenCalled();
  });

  it("stops itself at a minute, and says so", async () => {
    const onCapped = vi.fn();
    const recorder = await startRecording({ onCapped });

    clock += 59_999;
    vi.advanceTimersByTime(59_999);
    expect(FakeMediaRecorder.last?.state).toBe("recording");
    clock += 1;
    vi.advanceTimersByTime(1);

    expect(FakeMediaRecorder.last?.state).toBe("inactive");
    expect(onCapped).toHaveBeenCalledOnce();
    expect((await recorder.stop()).durationMs).toBe(60_000);
  });

  it("throws a cancelled recording away and still lets go of the microphone", async () => {
    const recorder = await startRecording();

    recorder.cancel();

    expect(track.stop).toHaveBeenCalled();
    await expect(recorder.stop()).rejects.toBeInstanceOf(RecorderError);
  });

  it.each([
    ["NotAllowedError", "denied"],
    ["SecurityError", "denied"],
    ["NotFoundError", "failed"],
  ])("says %s is %s", async (name, failure) => {
    microphone(() => Promise.reject(new DOMException("no", name)));

    await expect(startRecording()).rejects.toMatchObject({ failure });
  });

  it("is unsupported with no recorder, or no type the API takes", async () => {
    FakeMediaRecorder.supported = ["audio/wav"];
    await expect(startRecording()).rejects.toMatchObject({
      failure: "unsupported",
    });

    vi.stubGlobal("MediaRecorder", undefined);
    await expect(startRecording()).rejects.toMatchObject({
      failure: "unsupported",
    });
  });
});
