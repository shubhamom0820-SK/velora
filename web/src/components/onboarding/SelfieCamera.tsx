"use client";

import { useEffect, useEffectEvent, useRef, useState } from "react";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import {
  CameraError,
  captureFrame,
  openFrontCamera,
  stopCamera,
  type CameraFailure,
} from "@/lib/camera";

/** The circle a selfie is shown in, as the prototype's: 180 px. */
export const SELFIE_CIRCLE =
  "rounded-pill bg-surface flex size-[180px] items-center justify-center overflow-hidden border-2";

/**
 * The live front camera (T-4.7), mirrored as a mirror is, and the shutter, as
 * the prototype's `Cam`. The camera opens when this shows and is switched off
 * when it goes, whether a picture was taken, cancelled or the page left. The
 * picture taken isn't mirrored (src/lib/camera.ts).
 */
export function SelfieCamera({
  onCapture,
  onFailure,
}: {
  onCapture: (shot: Blob) => void;
  onFailure: (failure: CameraFailure) => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);
  const [taking, setTaking] = useState(false);
  const failed = useEffectEvent(onFailure);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let closed = false;
    openFrontCamera().then(
      (opened) => {
        // Closed while the browser asked: switched off at once.
        if (closed) {
          stopCamera(opened);
          return;
        }
        stream = opened;
        if (video.current) video.current.srcObject = opened;
      },
      (error: unknown) => {
        if (!closed)
          failed(error instanceof CameraError ? error.failure : "other");
      },
    );
    return () => {
      closed = true;
      stopCamera(stream);
    };
  }, []);

  async function take() {
    const element = video.current;
    if (!element) return;
    setTaking(true);
    const shot = await captureFrame(element);
    setTaking(false);
    if (shot) onCapture(shot);
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <div
        className={cx(
          SELFIE_CIRCLE,
          ready ? "border-accent shadow-2" : "border-line",
        )}
      >
        <video
          ref={video}
          autoPlay
          muted
          playsInline
          aria-label={t("onboarding.selfie.preview")}
          onLoadedData={() => setReady(true)}
          className="size-full -scale-x-100 object-cover"
        />
      </div>
      <button
        type="button"
        aria-label={t("onboarding.selfie.take")}
        disabled={!ready || taking}
        onClick={() => void take()}
        className="rounded-pill bg-accent border-bg shadow-1 disabled:bg-surface-2 focus-visible:outline-accent flex size-16 items-center justify-center border-[3px] focus-visible:outline-2 focus-visible:outline-offset-2 disabled:shadow-none"
      >
        <span className="rounded-pill bg-on-accent size-6" />
      </button>
      <p
        role="status"
        className="text-small text-mute max-w-[280px] text-center"
      >
        {ready ? t("onboarding.selfie.frame") : t("onboarding.selfie.opening")}
      </p>
    </div>
  );
}
