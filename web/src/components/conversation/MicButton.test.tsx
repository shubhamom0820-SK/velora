import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";

import { t } from "@/i18n/t";
import * as recorder from "@/lib/voice-recorder";

import { HOLD_MS, MicButton } from "./MicButton";

vi.mock("@/lib/voice-recorder", async (original) => ({
  ...(await original<typeof import("@/lib/voice-recorder")>()),
  startRecording: vi.fn(),
}));

const recording = (durationMs: number): recorder.Recording => ({
  blob: new Blob(["webm"], { type: "audio/webm" }),
  contentType: "audio/webm",
  durationMs,
});

let stop: Mock<() => Promise<recorder.Recording>>;
let cancel: Mock<() => void>;
let capped: (() => void) | undefined;

function setup(durationMs = 5_000) {
  stop = vi.fn(() => Promise.resolve(recording(durationMs)));
  cancel = vi.fn<() => void>();
  vi.mocked(recorder.startRecording).mockImplementation(async (options) => {
    capped = options?.onCapped;
    return { stop, cancel };
  });
  const onSend = vi.fn();
  const onNote = vi.fn();
  const onActiveChange = vi.fn();
  render(
    <MicButton
      onSend={onSend}
      onNote={onNote}
      onActiveChange={onActiveChange}
    />,
  );
  return { onSend, onNote, onActiveChange };
}

const mic = () =>
  screen.getByRole("button", {
    name: new RegExp(
      `^(${t("conversation.voice.record")}|${t("conversation.voice.stop")})$`,
    ),
  });

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
  vi.mocked(recorder.startRecording).mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("her mic (T-7.11)", () => {
  it("records while held and stops when let go, then plays it back before anything is sent", async () => {
    const { onSend, onActiveChange } = setup();
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000);

    fireEvent.pointerDown(mic(), { button: 0 });
    await screen.findByRole("button", { name: t("conversation.voice.stop") });
    now.mockReturnValue(1_000 + HOLD_MS + 600);
    fireEvent.pointerUp(mic());

    await screen.findByRole("button", { name: t("conversation.voice.send") });
    expect(stop).toHaveBeenCalledOnce();
    expect(onSend).not.toHaveBeenCalled();
    expect(document.querySelector("audio")?.getAttribute("src")).toBe(
      "blob:preview",
    );
    expect(onActiveChange).toHaveBeenLastCalledWith(true);

    await userEvent.click(
      screen.getByRole("button", { name: t("conversation.voice.send") }),
    );
    expect(onSend).toHaveBeenCalledWith(recording(5_000));
    expect(onActiveChange).toHaveBeenLastCalledWith(false);
    now.mockRestore();
  });

  it("keeps recording after a tap, until the second tap", async () => {
    setup();
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000);

    fireEvent.pointerDown(mic(), { button: 0 });
    await screen.findByRole("button", { name: t("conversation.voice.stop") });
    now.mockReturnValue(1_100);
    fireEvent.pointerUp(mic());
    await act(async () => {});
    expect(stop).not.toHaveBeenCalled();

    fireEvent.pointerDown(mic(), { button: 0 });
    fireEvent.pointerUp(mic());

    await screen.findByRole("button", { name: t("conversation.voice.send") });
    expect(stop).toHaveBeenCalledOnce();
    now.mockRestore();
  });

  it("starts and stops from the keyboard too", async () => {
    setup();

    fireEvent.keyDown(mic(), { key: "Enter" });
    await screen.findByRole("button", { name: t("conversation.voice.stop") });
    fireEvent.keyDown(mic(), { key: " " });

    await screen.findByRole("button", { name: t("conversation.voice.send") });
  });

  it("throws away anything under a second, and says why", async () => {
    const { onSend, onNote } = setup(600);

    fireEvent.keyDown(mic(), { key: "Enter" });
    await screen.findByRole("button", { name: t("conversation.voice.stop") });
    fireEvent.keyDown(mic(), { key: "Enter" });

    await waitFor(() =>
      expect(onNote).toHaveBeenLastCalledWith("conversation.voice.tooShort"),
    );
    expect(
      screen.queryByRole("button", { name: t("conversation.voice.send") }),
    ).not.toBeInTheDocument();
    expect(onSend).not.toHaveBeenCalled();
  });

  it("says when it stopped at the minute", async () => {
    const { onNote } = setup(60_000);

    fireEvent.keyDown(mic(), { key: "Enter" });
    await screen.findByRole("button", { name: t("conversation.voice.stop") });
    await act(async () => capped?.());

    await screen.findByRole("button", { name: t("conversation.voice.send") });
    expect(onNote).toHaveBeenLastCalledWith("conversation.voice.capped");
  });

  it.each([
    ["denied", "conversation.voice.denied"],
    ["unsupported", "conversation.voice.unsupported"],
    ["failed", "conversation.voice.failed"],
  ] as const)(
    "explains a microphone %s, recording nothing",
    async (failure, note) => {
      const onNote = vi.fn();
      vi.mocked(recorder.startRecording).mockRejectedValue(
        new recorder.RecorderError(failure),
      );
      render(
        <MicButton onSend={vi.fn()} onNote={onNote} onActiveChange={vi.fn()} />,
      );

      fireEvent.keyDown(mic(), { key: "Enter" });

      await waitFor(() => expect(onNote).toHaveBeenLastCalledWith(note));
      expect(mic()).toHaveAccessibleName(t("conversation.voice.record"));
    },
  );

  it("discards a recording, letting go of the microphone", async () => {
    const { onSend } = setup();

    fireEvent.keyDown(mic(), { key: "Enter" });
    await screen.findByRole("button", { name: t("conversation.voice.stop") });
    await userEvent.click(
      screen.getByRole("button", { name: t("conversation.voice.discard") }),
    );

    expect(cancel).toHaveBeenCalledOnce();
    expect(mic()).toHaveAccessibleName(t("conversation.voice.record"));
    expect(onSend).not.toHaveBeenCalled();
  });
});
