// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// T-9.11: colour contrast AA from the tokens (08-DESIGN §1). Every pair of
// text and ground the screens draw, read from tokens.css itself, never typed
// here, so a token moved below AA fails. Text needs 4.5:1 (WCAG 1.4.3; the
// screens' text is under 18.66 px bold, so none counts as large); the focus
// ring, a non-text mark, 3:1 against every ground it is drawn on (1.4.11).
// axe checks the rendered pages too (e2e/a11y.spec.ts); this holds the tokens.

const CSS = readFileSync(new URL("./tokens.css", import.meta.url), "utf8");

type Rgba = { r: number; g: number; b: number; a: number };

function token(name: string): Rgba {
  const match = new RegExp(`--${name}:\\s*([^;]+);`).exec(CSS);
  if (!match?.[1]) throw new Error(`no token --${name} in tokens.css`);
  const value = match[1].trim();
  const hex = /^#([0-9a-f]{6})$/i.exec(value);
  if (hex?.[1]) {
    const n = Number.parseInt(hex[1], 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255, a: 1 };
  }
  const rgba = /^rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)$/.exec(value);
  if (rgba) {
    const [, r, g, b, a] = rgba.map(Number);
    return { r: r ?? 0, g: g ?? 0, b: b ?? 0, a: a ?? 1 };
  }
  throw new Error(`--${name} is neither six-digit hex nor RGBA: ${value}`);
}

/** A colour as it shows over `under`: a tint is drawn on the ground beneath it. */
function over(top: Rgba, under: Rgba): Rgba {
  const mix = (t: number, u: number) => Math.round(top.a * t + (1 - top.a) * u);
  return {
    r: mix(top.r, under.r),
    g: mix(top.g, under.g),
    b: mix(top.b, under.b),
    a: 1,
  };
}

function luminance({ r, g, b }: Rgba): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function ratio(a: Rgba, b: Rgba): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

/** A ground by name; "accent-soft/bg" is the tint over --bg. */
function ground(name: string): Rgba {
  const [tint, base] = name.split("/");
  return base ? over(token(tint ?? ""), token(base)) : token(name);
}

// Text and the grounds it is drawn on.
const TEXT: ReadonlyArray<[string, string[]]> = [
  ["ink", ["page", "bg", "surface", "surface-2", "accent-soft/bg"]],
  ["mute", ["bg", "surface", "surface-2", "accent-soft/surface"]],
  ["accent", ["bg", "surface"]],
  ["accent-text", ["accent-soft/bg", "accent-soft/surface", "surface-2"]],
  ["on-accent", ["accent"]],
  ["chrome-ink", ["chrome", "chrome-line", "chrome-accent-soft/chrome"]],
  ["chrome-mute", ["chrome", "chrome-line"]],
  ["chrome-accent", ["chrome"]],
];

// The focus ring (D-962), as globals.css sets it: the token `--focus-ring`
// names in `:root`, the content's, and the one the chrome's grounds give it.
const GLOBALS = readFileSync(
  new URL("../app/globals.css", import.meta.url),
  "utf8",
);

function ringIn(selector: RegExp): string {
  const source = String.raw`\s*\{\s*--focus-ring:\s*var\(--([\w-]+)\);`;
  const found = new RegExp(selector.source + source).exec(GLOBALS)?.[1];
  if (!found)
    throw new Error(`globals.css sets no --focus-ring for ${selector}`);
  return found;
}

const CONTENT_RING = ringIn(/:root/);
const CHROME_RING = ringIn(/\.bg-chrome,\s*\.bg-chrome-line/);

// Every ground a control sits on, and the ring drawn there.
const RINGS: ReadonlyArray<[string, string, string]> = [
  ["in the content", CONTENT_RING, "page"],
  ["in the content", CONTENT_RING, "bg"],
  ["in the content", CONTENT_RING, "surface"],
  ["in the content", CONTENT_RING, "surface-2"],
  ["inside the chrome", CHROME_RING, "chrome"],
  ["inside the chrome", CHROME_RING, "chrome-line"],
];

describe("colour contrast from the tokens (T-9.11, 08-DESIGN §1)", () => {
  it.each(TEXT.flatMap(([text, grounds]) => grounds.map((g) => [text, g])))(
    "--%s text on --%s is at least 4.5:1",
    (text, on) => {
      expect(ratio(token(text ?? ""), ground(on ?? ""))).toBeGreaterThanOrEqual(
        4.5,
      );
    },
  );

  it.each(RINGS)(
    "the focus ring %s, --%s, is at least 3:1 on --%s",
    (_, ring, on) => {
      expect(ratio(token(ring), ground(on))).toBeGreaterThanOrEqual(3);
    },
  );

  it("is why the chrome has a ring of its own: --accent on --chrome-line is under 3:1", () => {
    expect(ratio(token("accent"), ground("chrome-line"))).toBeLessThan(3);
  });

  it("is why --accent-text exists: --accent on its own tint is under 4.5:1 (D-961)", () => {
    // Were this to pass, the brand red would do and the extra token could go.
    expect(ratio(token("accent"), ground("accent-soft/bg"))).toBeLessThan(4.5);
  });
});
