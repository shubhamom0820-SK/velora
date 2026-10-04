import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fitWithin,
  JPEG_QUALITY,
  MAX_SIDE_PX,
  resizeForUpload,
} from "./resize-image";

describe("fitWithin", () => {
  it.each([
    [
      { width: 4000, height: 3000 },
      { width: 2000, height: 1500 },
    ],
    [
      { width: 3024, height: 4032 },
      { width: 1500, height: 2000 },
    ],
    [
      { width: 2000, height: 2000 },
      { width: 2000, height: 2000 },
    ],
    [
      { width: 800, height: 600 },
      { width: 800, height: 600 },
    ],
    [
      { width: 9000, height: 2 },
      { width: 2000, height: 1 },
    ],
  ])("fits %o within 2000 px as %o, never enlarging", (size, fitted) => {
    expect(fitWithin(size, MAX_SIDE_PX)).toEqual(fitted);
  });
});

/** jsdom decodes no images: this one is as wide and tall as the test says. */
function fakeImages(size: { width: number; height: number } | "unreadable") {
  vi.stubGlobal(
    "Image",
    class {
      src = "";
      naturalWidth = size === "unreadable" ? 0 : size.width;
      naturalHeight = size === "unreadable" ? 0 : size.height;
      decode(): Promise<void> {
        return size === "unreadable"
          ? Promise.reject(new DOMException("can't decode", "EncodingError"))
          : Promise.resolve();
      }
    },
  );
}

type Drawn = { width: number; height: number; calls: string[] };

/** A canvas that records what's drawn and exports a JPEG-typed blob. */
function fakeCanvas(): Drawn {
  const drawn: Drawn = { width: 0, height: 0, calls: [] };
  const context = {
    set fillStyle(value: string) {
      drawn.calls.push(`fillStyle ${value}`);
    },
    fillRect: (...args: number[]) =>
      drawn.calls.push(`fillRect ${args.join(",")}`),
    drawImage: (_image: unknown, ...args: number[]) =>
      drawn.calls.push(`drawImage ${args.join(",")}`),
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(
    function (this: HTMLCanvasElement) {
      drawn.width = this.width;
      drawn.height = this.height;
      return context as unknown as CanvasRenderingContext2D;
    } as unknown as HTMLCanvasElement["getContext"],
  );
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
    (callback, type, quality) => {
      drawn.calls.push(`toBlob ${type} ${quality}`);
      callback(new Blob(["jpeg"], { type: type ?? "" }));
    },
  );
  return drawn;
}

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => "blob:http://127.0.0.1:3000/x");
  URL.revokeObjectURL = vi.fn();
  document.documentElement.style.setProperty("--surface", "white");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.documentElement.style.removeProperty("--surface");
});

describe("resizeForUpload (T-4.6)", () => {
  it("draws a large photo at 2000 px on its longest side and sends a JPEG", async () => {
    fakeImages({ width: 4032, height: 3024 });
    const drawn = fakeCanvas();

    const out = await resizeForUpload(
      new Blob(["heic"], { type: "image/heic" }),
    );

    expect(out?.type).toBe("image/jpeg");
    expect([drawn.width, drawn.height]).toEqual([2000, 1500]);
    expect(drawn.calls).toEqual([
      "fillStyle white",
      "fillRect 0,0,2000,1500",
      "drawImage 0,0,2000,1500",
      `toBlob image/jpeg ${JPEG_QUALITY}`,
    ]);
  });

  it("re-draws a small photo too, at its own size, so every upload is a JPEG", async () => {
    fakeImages({ width: 640, height: 480 });
    const drawn = fakeCanvas();

    const out = await resizeForUpload(new Blob(["png"], { type: "image/png" }));

    expect(out?.type).toBe("image/jpeg");
    expect([drawn.width, drawn.height]).toEqual([640, 480]);
  });

  it("gives back nothing for a file the browser can't read, so it goes up as it is", async () => {
    fakeImages("unreadable");
    const drawn = fakeCanvas();

    expect(await resizeForUpload(new Blob(["?"]))).toBeNull();
    expect(drawn.calls).toEqual([]);
  });

  it("lets go of the object URL it decoded from", async () => {
    fakeImages({ width: 10, height: 10 });
    fakeCanvas();

    await resizeForUpload(new Blob(["x"]));

    expect(URL.revokeObjectURL).toHaveBeenCalledWith(
      "blob:http://127.0.0.1:3000/x",
    );
  });
});
