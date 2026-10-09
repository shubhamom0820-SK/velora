"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { useNow } from "@/lib/ticker";
import {
  extensionOf,
  RecorderError,
  startRecording,
  type Recorder,
  type Recording,
} from "@/lib/voice-recorder";

const BROWSERS = ["chrome", "firefox", "safari"] as const;
const PLATFORMS = ["mac", "iphone"] as const;
const TARGETS = [5, 59] as const;

/**
 * `<browser>-<platform>-<target>s-<ms>ms.<ext>`: what was recorded where, and
 * the recorder's own length in milliseconds, which the API's measuring must
 * come within a second of (P-520).
 */
export function fileNameOf(
  browser: string,
  platform: string,
  target: number,
  recording: Recording,
): string {
  return `${browser}-${platform}-${target}s-${Math.round(recording.durationMs)}ms.${extensionOf(recording.contentType)}`;
}

/**
 * Records with the app's recorder and offers the file to save (a download,
 * or the share sheet on a phone, to AirDrop it to the Mac). Nothing is
 * uploaded anywhere.
 */
export function VoiceHarness() {
  const [browser, setBrowser] = useState<string>(BROWSERS[0]);
  const [platform, setPlatform] = useState<string>(PLATFORMS[0]);
  const [target, setTarget] = useState<number>(TARGETS[0]);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [message, setMessage] = useState("");
  const recorder = useRef<Recorder | null>(null);

  const url = useMemo(
    () => (recording ? URL.createObjectURL(recording.blob) : null),
    [recording],
  );
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  const name = recording
    ? fileNameOf(browser, platform, target, recording)
    : "";

  async function record() {
    setRecording(null);
    setMessage("");
    try {
      recorder.current = await startRecording({
        onCapped: () => void stop(),
      });
      setStartedAt(Date.now());
    } catch (error) {
      setMessage(
        `Couldn't record: ${error instanceof RecorderError ? error.failure : String(error)}`,
      );
    }
  }

  async function stop() {
    const active = recorder.current;
    recorder.current = null;
    setStartedAt(null);
    if (!active) return;
    try {
      setRecording(await active.stop());
    } catch (error) {
      setMessage(`Recording failed: ${String(error)}`);
    }
  }

  async function share() {
    if (!recording) return;
    const file = new File([recording.blob], name, {
      type: recording.contentType,
    });
    try {
      await navigator.share({ files: [file] });
    } catch (error) {
      setMessage(`Share failed: ${String(error)}`);
    }
  }

  const canShare =
    recording !== null &&
    typeof navigator !== "undefined" &&
    typeof navigator.canShare === "function" &&
    navigator.canShare({
      files: [
        new File([recording.blob], name, { type: recording.contentType }),
      ],
    });

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 p-6">
      <h1 className="text-title-1 text-ink">Voice recordings (P-520)</h1>
      <p className="text-small text-mute">
        Record with the app&apos;s recorder, then save the file. Count slowly or
        read something neutral: these files go into the repository.
      </p>
      <label className="text-small text-ink flex flex-col gap-1">
        Browser
        <select
          value={browser}
          onChange={(event) => setBrowser(event.target.value)}
          className="border-line bg-surface rounded-input border p-2"
        >
          {BROWSERS.map((each) => (
            <option key={each}>{each}</option>
          ))}
        </select>
      </label>
      <label className="text-small text-ink flex flex-col gap-1">
        Device
        <select
          value={platform}
          onChange={(event) => setPlatform(event.target.value)}
          className="border-line bg-surface rounded-input border p-2"
        >
          {PLATFORMS.map((each) => (
            <option key={each}>{each}</option>
          ))}
        </select>
      </label>
      <label className="text-small text-ink flex flex-col gap-1">
        Length to record
        <select
          value={target}
          onChange={(event) => setTarget(Number(event.target.value))}
          className="border-line bg-surface rounded-input border p-2"
        >
          {TARGETS.map((each) => (
            <option key={each} value={each}>
              {each} seconds
            </option>
          ))}
        </select>
      </label>
      {startedAt === null ? (
        <Button onClick={() => void record()}>Record</Button>
      ) : (
        <>
          <Elapsed since={startedAt} />
          <Button variant="danger" onClick={() => void stop()}>
            Stop
          </Button>
        </>
      )}
      {recording && url && (
        <section aria-label="The recording" className="flex flex-col gap-2">
          <audio controls src={url} />
          <dl className="text-small text-ink grid grid-cols-2 gap-1">
            <dt>Type</dt>
            <dd>{recording.contentType}</dd>
            <dt>Recorder&apos;s length</dt>
            <dd>{Math.round(recording.durationMs)} ms</dd>
            <dt>Size</dt>
            <dd>{recording.blob.size} bytes</dd>
            <dt>File</dt>
            <dd className="break-all">{name}</dd>
          </dl>
          <a
            href={url}
            download={name}
            className="text-accent text-ui font-semibold underline"
          >
            Save {name}
          </a>
          {canShare && (
            <Button variant="ghost" onClick={() => void share()}>
              Share (AirDrop to the Mac)
            </Button>
          )}
        </section>
      )}
      {message && (
        <p role="status" className="text-small text-accent">
          {message}
        </p>
      )}
    </main>
  );
}

function Elapsed({ since }: { since: number }) {
  const now = useNow();
  return (
    <p className="text-title-2 text-ink tabular-nums">
      {Math.floor((now - since) / 1000)} s
    </p>
  );
}
