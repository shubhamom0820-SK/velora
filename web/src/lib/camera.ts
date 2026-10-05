/**
 * The front camera, for the selfie (T-4.7): opened, a frame taken from it as a
 * JPEG, and, when it can't be opened, why, in words that say what to do.
 *
 * The browser asks the person first, and refuses outright on a page whose
 * Permissions-Policy denies the camera: `camera=(self)` (security-headers.ts)
 * is what lets it ask at all. Only a secure context has `mediaDevices`;
 * `http://127.0.0.1` is one, which is why local sign-in uses it (CLAUDE.md).
 */

import { fitWithin, JPEG_QUALITY, MAX_SIDE_PX } from "./resize-image";

/**
 * The front camera, asked for 1280 × 720. Without a size most browsers give
 * 640 × 480, small for comparing faces; `ideal` never fails a camera that has
 * less, it gets the nearest. No audio: nothing here records sound.
 */
export const SELFIE_CONSTRAINTS = {
  video: {
    facingMode: "user",
    width: { ideal: 1280 },
    height: { ideal: 720 },
  },
  audio: false,
} as const satisfies MediaStreamConstraints;

/**
 * Why the camera didn't open: the person or the browser said no (`denied`),
 * there's no camera (`none`), another app has it (`busy`), this browser has no
 * camera API here (`unsupported`), or something else (`other`).
 */
export type CameraFailure =
  "denied" | "none" | "busy" | "unsupported" | "other";

export class CameraError extends Error {
  readonly failure: CameraFailure;

  constructor(failure: CameraFailure) {
    super(`The camera didn't open: ${failure}.`);
    this.name = "CameraError";
    this.failure = failure;
  }
}

/** What a `getUserMedia` refusal means, by its DOMException name. */
export function cameraFailure(error: unknown): CameraFailure {
  const name =
    error && typeof error === "object" && "name" in error ? error.name : null;
  switch (name) {
    // The person said no, or a policy did (a Permissions-Policy without the
    // camera reaches script as NotAllowedError in Chromium).
    case "NotAllowedError":
    case "SecurityError":
      return "denied";
    case "NotFoundError":
    case "OverconstrainedError":
      return "none";
    // In use by another app, or the system wouldn't start it.
    case "NotReadableError":
    case "AbortError":
      return "busy";
    default:
      return "other";
  }
}

/** Open the front camera, or throw `CameraError` saying why it didn't. */
export async function openFrontCamera(): Promise<MediaStream> {
  const media =
    typeof navigator === "undefined" ? undefined : navigator.mediaDevices;
  if (typeof media?.getUserMedia !== "function") {
    throw new CameraError("unsupported");
  }
  try {
    return await media.getUserMedia(SELFIE_CONSTRAINTS);
  } catch (error) {
    throw new CameraError(cameraFailure(error));
  }
}

/** Switch the camera off: its light goes out and the browser lets it go. */
export function stopCamera(stream: MediaStream | null): void {
  for (const track of stream?.getTracks() ?? []) track.stop();
}

/**
 * The frame the video shows now, as a JPEG at most 2000 px, or null if there
 * isn't one yet. The picture as the camera sees it: the preview is mirrored
 * for the person, the selfie isn't, as their photos aren't. A canvas writes no
 * EXIF, so no location goes up with it either (CLAUDE.md rule 15).
 */
export async function captureFrame(
  video: HTMLVideoElement,
): Promise<Blob | null> {
  if (video.videoWidth === 0 || video.videoHeight === 0) return null;
  const { width, height } = fitWithin(
    { width: video.videoWidth, height: video.videoHeight },
    MAX_SIDE_PX,
  );
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.drawImage(video, 0, 0, width, height);
  return new Promise((resolve) => {
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY);
  });
}

/**
 * Whose instructions to show when the camera is refused, by browser: each
 * browser keeps a site's camera permission in a different place.
 * - `ios`: every browser on an iPhone or iPad (all are WebKit there); an
 *   iPad asking for the desktop site says "Macintosh", but has a touch screen.
 * - `chrome-android`, `chrome-desktop`: Chrome itself. Edge, Samsung Internet
 *   and Opera say "Chrome" too, but their menus differ, so they get `other`.
 * - `safari-mac`, `firefox` (desktop: its Android menus differ).
 */
export type CameraBrowser =
  | "ios"
  | "chrome-android"
  | "chrome-desktop"
  | "safari-mac"
  | "firefox"
  | "other";

export function cameraBrowser(
  userAgent: string,
  maxTouchPoints = 0,
): CameraBrowser {
  if (
    /iPhone|iPad|iPod/.test(userAgent) ||
    (/Macintosh/.test(userAgent) && maxTouchPoints > 1)
  )
    return "ios";
  if (/Edg\/|EdgA\/|SamsungBrowser\/|OPR\/|Opera/.test(userAgent))
    return "other";
  if (/Chrome\//.test(userAgent))
    return /Android/.test(userAgent) ? "chrome-android" : "chrome-desktop";
  if (/Firefox\//.test(userAgent))
    return /Android|Mobile/.test(userAgent) ? "other" : "firefox";
  if (/Macintosh/.test(userAgent) && /Safari\//.test(userAgent))
    return "safari-mac";
  return "other";
}
