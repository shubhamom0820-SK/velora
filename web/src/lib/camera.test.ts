import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CameraError,
  cameraBrowser,
  cameraFailure,
  captureFrame,
  openFrontCamera,
  SELFIE_CONSTRAINTS,
  stopCamera,
} from "./camera";
import { JPEG_QUALITY } from "./resize-image";

/** `navigator.mediaDevices` as a browser has it, or none (an insecure page). */
function fakeMediaDevices(getUserMedia?: () => Promise<MediaStream>) {
  Object.defineProperty(navigator, "mediaDevices", {
    value: getUserMedia ? { getUserMedia: vi.fn(getUserMedia) } : undefined,
    configurable: true,
  });
  return navigator.mediaDevices as unknown as {
    getUserMedia: ReturnType<typeof vi.fn>;
  };
}

function fakeStream(tracks = 2) {
  const stops = Array.from({ length: tracks }, () => vi.fn());
  const stream = {
    getTracks: () => stops.map((stop) => ({ stop })),
  } as unknown as MediaStream;
  return { stream, stops };
}

afterEach(() => {
  Reflect.deleteProperty(navigator, "mediaDevices");
  vi.restoreAllMocks();
});

describe("opening the front camera (T-4.7)", () => {
  it("asks for the front camera at 1280 × 720 at best, and never the microphone", async () => {
    const { stream } = fakeStream();
    const media = fakeMediaDevices(async () => stream);

    await expect(openFrontCamera()).resolves.toBe(stream);
    expect(media.getUserMedia).toHaveBeenCalledWith(SELFIE_CONSTRAINTS);
    expect(SELFIE_CONSTRAINTS).toEqual({
      video: {
        facingMode: "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });
  });

  it("says the browser can't, where there's no camera API (an insecure page)", async () => {
    fakeMediaDevices();

    await expect(openFrontCamera()).rejects.toEqual(
      new CameraError("unsupported"),
    );
  });

  it.each([
    ["NotAllowedError", "denied"],
    ["SecurityError", "denied"],
    ["NotFoundError", "none"],
    ["OverconstrainedError", "none"],
    ["NotReadableError", "busy"],
    ["AbortError", "busy"],
    ["TypeError", "other"],
  ] as const)("reads %s as %s", async (name, failure) => {
    fakeMediaDevices(() => Promise.reject(new DOMException("no", name)));

    const error = await openFrontCamera().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(CameraError);
    expect((error as CameraError).failure).toBe(failure);
    expect(cameraFailure(new DOMException("no", name))).toBe(failure);
  });

  it("reads anything that isn't an error as other", () => {
    expect(cameraFailure("no")).toBe("other");
    expect(cameraFailure(null)).toBe("other");
  });
});

describe("switching it off", () => {
  it("stops every track, and is harmless with none", () => {
    const { stream, stops } = fakeStream(2);

    stopCamera(stream);
    stopCamera(null);

    for (const stop of stops) expect(stop).toHaveBeenCalledOnce();
  });
});

describe("taking a frame", () => {
  function video(width: number, height: number): HTMLVideoElement {
    const element = document.createElement("video");
    Object.defineProperty(element, "videoWidth", { value: width });
    Object.defineProperty(element, "videoHeight", { value: height });
    return element;
  }

  function fakeCanvas() {
    const drawn: string[] = [];
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
      function (this: HTMLCanvasElement) {
        return {
          drawImage: (_source: unknown, ...args: number[]) =>
            drawn.push(
              `drawImage ${args.join(",")} on ${this.width}x${this.height}`,
            ),
          // Anything that would mirror the picture.
          scale: () => drawn.push("scale"),
          setTransform: () => drawn.push("setTransform"),
          translate: () => drawn.push("translate"),
        } as unknown as CanvasRenderingContext2D;
      } as unknown as HTMLCanvasElement["getContext"],
    );
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
      (callback, type, quality) => {
        drawn.push(`toBlob ${type} ${quality}`);
        callback(new Blob(["jpeg"], { type: type ?? "" }));
      },
    );
    return drawn;
  }

  it("draws the frame as the camera sees it, never mirrored, as a JPEG", async () => {
    const drawn = fakeCanvas();

    const shot = await captureFrame(video(1280, 720));

    expect(shot?.type).toBe("image/jpeg");
    expect(drawn).toEqual([
      "drawImage 0,0,1280,720 on 1280x720",
      `toBlob image/jpeg ${JPEG_QUALITY}`,
    ]);
  });

  it("keeps a larger camera's frame within 2000 px", async () => {
    const drawn = fakeCanvas();

    await captureFrame(video(3840, 2160));

    expect(drawn[0]).toBe("drawImage 0,0,2000,1125 on 2000x1125");
  });

  it("gives nothing before the camera has shown a frame", async () => {
    const drawn = fakeCanvas();

    await expect(captureFrame(video(0, 0))).resolves.toBeNull();
    expect(drawn).toEqual([]);
  });
});

describe("whose instructions a blocked camera gets", () => {
  it.each([
    [
      "Safari on an iPhone",
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1",
      0,
      "ios",
    ],
    [
      "Chrome on an iPhone",
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/140.0.7339.122 Mobile/15E148 Safari/604.1",
      0,
      "ios",
    ],
    [
      "an iPad asking for the desktop site",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
      5,
      "ios",
    ],
    [
      "Chrome on Android",
      "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
      5,
      "chrome-android",
    ],
    [
      "Samsung Internet",
      "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
      5,
      "other",
    ],
    [
      "Edge on a computer",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
      0,
      "other",
    ],
    [
      "Chrome on a Mac",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
      0,
      "chrome-desktop",
    ],
    [
      "Chrome on Windows",
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
      0,
      "chrome-desktop",
    ],
    [
      "Safari on a Mac",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
      0,
      "safari-mac",
    ],
    [
      "Firefox on a computer",
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0",
      0,
      "firefox",
    ],
    [
      "Firefox on Android, whose menus differ",
      "Mozilla/5.0 (Android 14; Mobile; rv:143.0) Gecko/143.0 Firefox/143.0",
      5,
      "other",
    ],
    ["anything else", "SomeBrowser/1.0", 0, "other"],
  ] as const)("%s", (_name, userAgent, touchPoints, browser) => {
    expect(cameraBrowser(userAgent, touchPoints)).toBe(browser);
  });
});
