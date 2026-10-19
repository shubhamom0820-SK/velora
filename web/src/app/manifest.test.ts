// @vitest-environment node
import { readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";

import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import { THEME_COLOR } from "@/styles/theme-color";

import manifest from "./manifest";

type Image = {
  width: number;
  height: number;
  pixel: (x: number, y: number) => number[];
};

/**
 * An 8-bit RGB or RGBA, non-interlaced PNG's pixels, as the icon script
 * writes them: just enough of the format to read an icon back.
 */
function decodePng(png: Buffer): Image {
  const width = png.readUInt32BE(16);
  const height = png.readUInt32BE(20);
  const depth = png[24];
  const colourType = png[25];
  const interlace = png[28];
  if (
    depth !== 8 ||
    (colourType !== 2 && colourType !== 6) ||
    interlace !== 0
  ) {
    throw new Error(`unexpected PNG: depth ${depth}, type ${colourType}`);
  }
  const channels = colourType === 6 ? 4 : 3;
  const chunks: Buffer[] = [];
  for (let at = 8; at < png.length;) {
    const length = png.readUInt32BE(at);
    const type = png.toString("latin1", at + 4, at + 8);
    if (type === "IDAT") chunks.push(png.subarray(at + 8, at + 8 + length));
    at += 12 + length;
  }
  const raw = inflateSync(Buffer.concat(chunks));
  const stride = width * channels;
  const out = Buffer.alloc(height * stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)];
    for (let x = 0; x < stride; x += 1) {
      const value = raw[y * (stride + 1) + 1 + x] ?? 0;
      const left = x >= channels ? (out[y * stride + x - channels] ?? 0) : 0;
      const up = y > 0 ? (out[(y - 1) * stride + x] ?? 0) : 0;
      const upLeft =
        y > 0 && x >= channels
          ? (out[(y - 1) * stride + x - channels] ?? 0)
          : 0;
      let predicted = 0;
      if (filter === 1) predicted = left;
      else if (filter === 2) predicted = up;
      else if (filter === 3) predicted = Math.floor((left + up) / 2);
      else if (filter === 4) {
        const p = left + up - upLeft;
        const [pa, pb, pc] = [p - left, p - up, p - upLeft].map(Math.abs);
        predicted = pa! <= pb! && pa! <= pc! ? left : pb! <= pc! ? up : upLeft;
      }
      out[y * stride + x] = (value + predicted) & 0xff;
    }
  }
  return {
    width,
    height,
    pixel: (x, y) => [
      ...out.subarray(
        (y * width + x) * channels,
        (y * width + x) * channels + 3,
      ),
    ],
  };
}

function hex(colour: string): number[] {
  const value = colour.replace("#", "");
  return [0, 2, 4].map((at) => parseInt(value.slice(at, at + 2), 16));
}

const TOKENS = readFileSync("src/styles/tokens.css", "utf8");
const CHROME_INK = /--chrome-ink:\s*([^;]+);/.exec(TOKENS)?.[1]?.trim() ?? "";

function icon(src: string): Image {
  return decodePng(readFileSync(`public${src}`));
}

describe("the web app manifest (T-9.7, D-1043)", () => {
  it("is exactly what installing the app needs", () => {
    expect(manifest()).toEqual({
      id: "/",
      name: APP_NAME,
      short_name: APP_NAME,
      description: t("meta.description"),
      lang: "en",
      start_url: "/discover",
      scope: "/",
      display: "standalone",
      theme_color: THEME_COLOR,
      background_color: THEME_COLOR,
      icons: [
        { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
        {
          src: "/icons/icon-maskable-512.png",
          sizes: "512x512",
          type: "image/png",
          purpose: "maskable",
        },
      ],
    });
  });

  it.each(manifest().icons ?? [])(
    "$src is the size it says",
    ({ src, sizes }) => {
      const image = icon(src);
      expect(`${image.width}x${image.height}`).toBe(sizes);
    },
  );

  it.each(manifest().icons ?? [])(
    "$src is the V in --chrome-ink on --chrome",
    ({ src }) => {
      const image = icon(src);
      const middle = Math.floor(image.width / 2);
      expect(image.pixel(0, 0)).toEqual(hex(THEME_COLOR));
      expect(image.pixel(image.width - 1, image.height - 1)).toEqual(
        hex(THEME_COLOR),
      );
      // The V's two strokes cross the middle row, in --chrome-ink.
      const row = Array.from({ length: image.width }, (_, x) =>
        image.pixel(x, middle).join(","),
      );
      expect(row).toContain(hex(CHROME_INK).join(","));
    },
  );

  it("keeps the maskable icon's whole V inside the centre 80% a launcher may crop to", () => {
    const image = icon("/icons/icon-maskable-512.png");
    const centre = image.width / 2;
    const safe = image.width * 0.4;
    const ground = hex(THEME_COLOR).join(",");
    let ink = 0;
    let outside = 0;
    for (let y = 0; y < image.height; y += 1) {
      for (let x = 0; x < image.width; x += 1) {
        if (image.pixel(x, y).join(",") === ground) continue;
        ink += 1;
        if (Math.hypot(x + 0.5 - centre, y + 0.5 - centre) > safe) outside += 1;
      }
    }
    expect(ink).toBeGreaterThan(0);
    expect(outside).toBe(0);
  });
});
