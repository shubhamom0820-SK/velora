import { existsSync, readFileSync } from "node:fs";

import type { Metadata, ResolvingMetadata } from "next";
import { describe, expect, it } from "vitest";

import { homeTitle } from "@/lib/site";

import { metadata as appGroup } from "./(app)/layout";
import { metadata as authGroup } from "./(auth)/layout";
import { metadata as adminGroup } from "./admin/layout";
import { generateMetadata as contact } from "./(marketing)/contact/page";
import { generateMetadata as home } from "./(marketing)/page";
import { generateMetadata as privacy } from "./(marketing)/privacy/page";
import { generateMetadata as refunds } from "./(marketing)/refunds/page";
import { generateMetadata as terms } from "./(marketing)/terms/page";

describe("pages that never belong in search results", () => {
  it.each([
    ["(app)", appGroup],
    ["(auth)", authGroup],
    ["/admin", adminGroup],
  ])("%s says noindex, in every environment", (_, metadata: Metadata) => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});

const NO_PARENT = Promise.resolve({
  openGraph: null,
}) as unknown as ResolvingMetadata;

describe("each public page's own metadata", () => {
  const pages = [
    ["/", home],
    ["/terms", terms],
    ["/privacy", privacy],
    ["/refunds", refunds],
    ["/contact", contact],
  ] as const;

  it.each(pages)(
    "%s has its own canonical address and a description",
    async (path, page) => {
      const metadata = await page({}, NO_PARENT);

      expect(metadata.alternates).toEqual({ canonical: path });
      expect(metadata.openGraph).toMatchObject({ url: path });
      expect(String(metadata.description).length).toBeGreaterThan(40);
    },
  );

  it("gives every page a different title and description", async () => {
    const all = await Promise.all(pages.map(([, page]) => page({}, NO_PARENT)));

    const titles = all.map((m) => JSON.stringify(m.title));
    const descriptions = all.map((m) => m.description);
    expect(new Set(titles).size).toBe(pages.length);
    expect(new Set(descriptions).size).toBe(pages.length);
  });
});

// --- The image files Next serves beside the root layout -----------------------

function jpegSize(bytes: Buffer): { width: number; height: number } {
  expect(bytes.subarray(0, 2)).toEqual(Buffer.from([0xff, 0xd8]));
  let at = 2;
  while (at < bytes.length) {
    const marker = bytes[at + 1] ?? 0;
    if (marker >= 0xc0 && marker <= 0xc3) {
      return {
        height: bytes.readUInt16BE(at + 5),
        width: bytes.readUInt16BE(at + 7),
      };
    }
    at += 2 + bytes.readUInt16BE(at + 2);
  }
  throw new Error("No frame header: not a JPEG Next can size.");
}

const PNG_SIGNATURE = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
]);

function pngHeader(bytes: Buffer) {
  expect(bytes.subarray(0, 8)).toEqual(PNG_SIGNATURE);
  return {
    width: bytes.readUInt32BE(16),
    height: bytes.readUInt32BE(20),
    // 6 is RGBA, which Next requires inside favicon.ico.
    colourType: bytes[25],
  };
}

describe("the share image", () => {
  const image = readFileSync("src/app/opengraph-image.jpg");

  it("is 1200 x 630, the size every link preview expects", () => {
    expect(jpegSize(image)).toEqual({ width: 1200, height: 630 });
  });

  it("stays small: only crawlers fetch it, and WhatsApp drops large previews", () => {
    expect(image.length).toBeLessThan(100 * 1024);
  });

  it("is the only one, so there's no doubt which Next uses", () => {
    expect(existsSync("src/app/opengraph-image.png")).toBe(false);
  });

  // The headline is baked into the image's pixels. Its alt text says the same
  // words, so changing the headline in en.ts fails here, and whoever changes it
  // regenerates the image beside this file (08-DESIGN §7).
  it("has alt text saying exactly what the image says: the brand and the headline", () => {
    expect(readFileSync("src/app/opengraph-image.alt.txt", "utf8").trim()).toBe(
      homeTitle(),
    );
  });
});

describe("the icons", () => {
  it("apple-icon.png is 180 x 180", () => {
    expect(pngHeader(readFileSync("src/app/apple-icon.png"))).toMatchObject({
      width: 180,
      height: 180,
    });
  });

  it("favicon.ico holds 16, 32 and 48 px images, each an RGBA PNG", () => {
    const ico = readFileSync("src/app/favicon.ico");
    expect(ico.readUInt16LE(2)).toBe(1); // an icon, not a cursor
    const count = ico.readUInt16LE(4);
    const sizes = Array.from({ length: count }, (_, i) => {
      const entry = 6 + 16 * i;
      const length = ico.readUInt32LE(entry + 8);
      const offset = ico.readUInt32LE(entry + 12);
      const png = pngHeader(ico.subarray(offset, offset + length));
      expect(png.colourType).toBe(6);
      expect([png.width, png.height]).toEqual([ico[entry], ico[entry + 1]]);
      return png.width;
    });
    expect(sizes).toEqual([16, 32, 48]);
  });
});
