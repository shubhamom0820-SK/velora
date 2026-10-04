// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// T-5.6: the shell's look lives in two places only. Colour, type scale and
// sizes are tokens in src/styles/tokens.css; the header's and nav's shape is
// AppShell.tsx, never spread through components inside it. So T-6.5's design
// pass (P-57) changes values, not structure. Colours are already held to
// tokens.css by the pre-commit hook, and Tailwind's palette doesn't compile
// (globals.css); this holds the rest.

const tokensCss = readFileSync(
  new URL("../../styles/tokens.css", import.meta.url),
  "utf8",
);
const TOKENS = new Set(
  [...tokensCss.matchAll(/(--[\w-]+)\s*:/g)].map(([, name = ""]) => name),
);

// A class that carries a look value of its own instead of reading a token.
// Matched against a class with its variants (`md:`), `!` and `-` stripped.
const LOOK_CLASSES: ReadonlyArray<[RegExp, string]> = [
  [
    /^(p[xytrblse]?|m[xytrblse]?|gap(-[xy])?|space-[xy]|w|h|size|min-w|min-h|max-w|max-h|inset(-[xy])?|top|right|bottom|left|start|end|basis|indent|translate-[xy])-(\d|px$)/,
    "a size from Tailwind's scale",
  ],
  [
    /^(w|min-w|max-w)-(3xs|2xs|xs|sm|md|lg|xl|\dxl|prose|screen)/,
    "a named width",
  ],
  [/^text-(xs|sm|base|lg|xl|\dxl)$/, "Tailwind's type scale"],
  [/^(leading|tracking)-/, "a line height or tracking"],
  [
    /^font-(thin|extralight|light|normal|medium|semibold|bold|extrabold|black)$/,
    "a font weight",
  ],
  [
    /^rounded(-(t|r|b|l|s|e|tl|tr|br|bl|ss|se|es|ee))?(-(none|xs|sm|md|lg|xl|\dxl|full))?$/,
    "Tailwind's radius",
  ],
  [
    /^(border(-[xytrblse])?|outline|outline-offset|ring|ring-offset|divide-[xy]|stroke)-\d/,
    "a line width",
  ],
  [/^shadow(-(2xs|xs|sm|md|lg|xl|2xl|inner|none))?$/, "Tailwind's shadow"],
  [/^opacity-\d|\/\d+$/, "an opacity"],
];

// A look value written into the JSX itself.
const LOOK_PROPS: ReadonlyArray<[RegExp, string]> = [
  [/\b(size|strokeWidth|width|height)=\{\s*[\d.]/, "a number passed as a size"],
  [/\bstyle=\{/, "an inline style"],
];

function withoutComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Every look value in `source` that isn't a token, with why. */
function lookViolations(source: string): string[] {
  const code = withoutComments(source);
  const found: string[] = [];
  const literals = code.matchAll(/"([^"\\]*)"|'([^'\\]*)'|`([^`]*)`/g);
  for (const [, double, single, template] of literals) {
    for (const token of (double ?? single ?? template ?? "").split(/\s+/)) {
      if (token === "") continue;
      if (token.includes("[")) {
        found.push(`${token}: an arbitrary value`);
        continue;
      }
      const utility = token
        .replace(/^([^:]*:)+/, "")
        .replace(/^!|!$/g, "")
        .replace(/^-/, "");
      if (/-0$/.test(utility)) continue; // zero is no look
      for (const [pattern, why] of LOOK_CLASSES) {
        if (pattern.test(utility)) found.push(`${token}: ${why}`);
      }
    }
  }
  for (const [pattern, why] of LOOK_PROPS) {
    const match = pattern.exec(code);
    if (match) found.push(`${match[0]}: ${why}`);
  }
  for (const [, name = ""] of code.matchAll(/(?:\(|var\()\s*(--[\w-]+)/g)) {
    if (!TOKENS.has(name)) found.push(`${name}: not a token in tokens.css`);
  }
  return found;
}

const SHELL_DIR = new URL("./", import.meta.url);
const shellSources = readdirSync(SHELL_DIR)
  .filter((file) => /\.tsx?$/.test(file) && !/\.test\.tsx?$/.test(file))
  .map((file) => ({
    file,
    source: readFileSync(new URL(file, SHELL_DIR), "utf8"),
  }));

describe("the shell's look (T-5.6)", () => {
  it("takes every size, type step and radius in AppShell.tsx from a token", () => {
    const shell = shellSources.find(({ file }) => file === "AppShell.tsx");
    expect(shell).toBeDefined();
    expect(lookViolations(shell?.source ?? "")).toEqual([]);
  });

  it("reads the shell's own tokens from tokens.css", () => {
    const shell = shellSources.find(({ file }) => file === "AppShell.tsx");
    const used = new Set(
      [...(shell?.source ?? "").matchAll(/\((--shell-[\w-]+)\)/g)].map(
        ([, name]) => name,
      ),
    );
    expect([...used].sort()).toEqual(
      [...TOKENS].filter((name) => name.startsWith("--shell-")).sort(),
    );
  });

  it("keeps the shape in AppShell.tsx: nothing else in shell/ has a class", () => {
    const others = shellSources
      .filter(({ file }) => file !== "AppShell.tsx")
      .filter(({ source }) => /\bclassName\b/.test(withoutComments(source)));
    expect(others.map(({ file }) => file)).toEqual([]);
  });
});

// The check proved both ways, so a pattern that matches nothing can't pass.
describe("the look check", () => {
  it.each([
    "px-5",
    "md:h-14",
    "gap-2",
    "max-w-225",
    "max-w-md",
    "text-sm",
    "text-[13px]",
    "tracking-tight",
    "font-bold",
    "rounded-lg",
    "rounded",
    "border-t-2",
    "shadow-md",
    "bg-chrome/80",
    "-mt-4",
  ])("flags %s", (cls) => {
    expect(lookViolations(`<div className="${cls}" />`)).toHaveLength(1);
  });

  it.each([
    ["a number as an icon's size", "<Icon icon={Heart} size={19} />"],
    ["an inline style", "<div style={{ padding: 4 }} />"],
    ["a token that doesn't exist", '<div className="h-(--shell-nope)" />'],
  ])("flags %s", (_, source) => {
    expect(lookViolations(source)).toHaveLength(1);
  });

  it.each([
    "h-(--shell-header-height) px-(--shell-gutter) md:px-(--shell-gutter)",
    "text-micro text-title-1 bg-chrome text-chrome-accent border-chrome-line",
    "flex flex-1 flex-col items-center md:flex-none md:self-stretch",
    "fixed inset-x-0 bottom-0 top-0 z-10 md:pb-0 md:border-t-0 border-b",
    "mx-auto min-h-dvh max-w-(--shell-width) md:h-auto fill-current",
    "rounded-pill rounded-button shadow-1",
  ])("allows %s", (classes) => {
    expect(lookViolations(`<div className="${classes}" />`)).toEqual([]);
  });

  it("ignores comments, where tokens are named in prose", () => {
    expect(
      lookViolations(
        '/* `--shell-*` and "px-5" */\n// "text-sm"\nconst a = 1;',
      ),
    ).toEqual([]);
  });
});
