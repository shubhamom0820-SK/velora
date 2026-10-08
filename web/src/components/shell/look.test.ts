// @vitest-environment node
import { readdirSync, readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// T-5.6: the shell's look lives in two places only. Colour, type scale and
// sizes are tokens in src/styles/tokens.css; the header's and nav's shape is
// AppShell.tsx, never spread through components inside it. So T-6.5's design
// pass (P-57) changes values, not structure.
//
// An allowlist (P-83): a class passes only if it carries no look of its own
// (LAYOUT), is named after a token, or reads one by `(--name)`. Anything else
// fails, including the families nobody has thought of yet: a blacklist passes
// every test written with today's names (D-084).

const read = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const TOKENS = new Set(
  [...read("../../styles/tokens.css").matchAll(/(--[\w-]+)\s*:/g)].map(
    ([, name = ""]) => name,
  ),
);

// The utilities each of globals.css's theme namespaces makes: `--color-bg`
// makes `bg-bg`, `text-bg`, `border-bg`. The names are read from the CSS,
// never typed here; `--text-micro--line-height` names no utility of its own.
const ROOTS: Record<string, string> = {
  color:
    "bg|text|border(?:-[xytrblse])?|fill|stroke|outline|ring|divide|decoration|caret|placeholder",
  text: "text",
  radius: "rounded(?:-(?:t|r|b|l|s|e|tl|tr|br|bl|ss|se|es|ee))?",
  shadow: "shadow",
  font: "font",
  animate: "animate",
};
const THEME_UTILITIES: RegExp[] = [
  ...read("../../app/globals.css").matchAll(
    /^\s*--(color|text|radius|shadow|font|animate)-([a-z0-9]+(?:-[a-z0-9]+)*)\s*:/gm,
  ),
].map(
  ([, space = "", name = ""]) => new RegExp(`^(?:${ROOTS[space]})-${name}$`),
);

// Classes that carry no look: display, position, flex and alignment, stacking
// order, zero, and "fill what's there". Matched with variants (`md:`), `!` and
// a leading `-` stripped.
const LAYOUT: RegExp[] = [
  /^(block|inline|inline-block|flex|inline-flex|grid|inline-grid|contents|hidden|sr-only|not-sr-only)$/,
  /^(static|fixed|absolute|relative|sticky)$/,
  /^(flex-(1|auto|initial|none|row|col|row-reverse|col-reverse|wrap|nowrap)|grow|grow-0|shrink|shrink-0)$/,
  /^(items|self|justify|justify-items|justify-self|content|place-items|place-self|place-content)-(start|end|center|stretch|baseline|between|around|evenly|auto|normal)$/,
  /^z-(\d+|auto)$/,
  /^(inset(-[xy])?|top|right|bottom|left|start|end|[pm][xytrblse]?|gap(-[xy])?|border(-[xytrblse])?)-0$/,
  /^m[xytrblse]?-auto$/,
  /^(w|h|min-w|min-h|max-w|max-h|size|basis)-(auto|full|screen|dvh|svh|lvh|dvw|svw|lvw|fit|min|max|none)$/,
  /^(fill|stroke)-(current|none)$/,
  /^overflow(-[xy])?-(auto|hidden|clip|visible|scroll)$/,
];

// A token read by name: `h-(--shell-header-height)`, `border-(length:--x)`.
const TOKEN_REFERENCE = /^[a-z][a-z0-9-]*-\((?:[a-z-]+:)?(--[\w-]+)\)$/;

// A look value written into the JSX itself.
const LOOK_PROPS: ReadonlyArray<[RegExp, string]> = [
  [/\b(size|strokeWidth|width|height)=\{\s*[\d.]/, "a number passed as a size"],
  [/\bstyle=\{/, "an inline style"],
];

function withoutComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Why `token`, one class, isn't allowed in the shell, or null if it is. */
function classViolation(token: string): string | null {
  if (token.includes("[")) return `${token}: an arbitrary value`;
  const utility = token
    .replace(/^([a-z0-9-]+:)+/, "")
    .replace(/^!|!$/g, "")
    .replace(/^-/, "");
  const reference = TOKEN_REFERENCE.exec(utility);
  if (reference) {
    const name = reference[1] ?? "";
    return TOKENS.has(name) ? null : `${token}: ${name} is not in tokens.css`;
  }
  if (LAYOUT.some((pattern) => pattern.test(utility))) return null;
  if (THEME_UTILITIES.some((pattern) => pattern.test(utility))) return null;
  return `${token}: not a layout class, a token's name or a token`;
}

// A class list the guard can read: one string, or `cx()` of strings, each
// alone or behind a plain name (`current && "…"`, `current ? "…" : "…"`).
// Strings stand as S here. Anything else, a variable, a call, a template with
// `${}`, hides its classes from the guard, so it fails.
const STRING = /"[^"\\]*"|'[^'\\]*'|`[^`$\\]*`/g;
const ARG = "(?:S|!?[\\w.]+&&S|!?[\\w.]+\\?S:S)";
const READABLE = new RegExp(`^(?:S|cx\\(${ARG}(?:,${ARG})*,?\\))$`);

/** The end of the `{…}` that opens at `start`, braces balanced. */
function closingBrace(code: string, start: number): number {
  let depth = 0;
  for (let i = start; i < code.length; i++) {
    if (code[i] === "{") depth++;
    if (code[i] === "}" && --depth === 0) return i;
  }
  return code.length;
}

/** Every look value in `source` that isn't a token, with why. */
function lookViolations(source: string): string[] {
  const code = withoutComments(source);
  const found: string[] = [];
  // Every prop or key that takes classes, `className` or `iconClassName`.
  for (const match of code.matchAll(/\w*[cC]lass[nN]ame\b\s*(=\s*)?/g)) {
    const at = (match.index ?? 0) + match[0].length;
    let value: string | null = null;
    if (match[1] !== undefined && (code[at] === '"' || code[at] === "'")) {
      value = code.slice(at, code.indexOf(code[at] ?? "", at + 1) + 1);
    } else if (match[1] !== undefined && code[at] === "{") {
      value = code.slice(at + 1, closingBrace(code, at));
    }
    const shape = (value ?? "").replace(STRING, "S").replace(/\s+/g, "");
    if (value === null || !READABLE.test(shape)) {
      found.push(
        `${match[0].trim()}${value ?? ""}: classes the guard can't read`,
      );
      continue;
    }
    for (const literal of value.match(STRING) ?? []) {
      for (const token of literal.slice(1, -1).split(/\s+/)) {
        if (token === "") continue;
        const why = classViolation(token);
        if (why) found.push(why);
      }
    }
  }
  for (const [pattern, why] of LOOK_PROPS) {
    const match = pattern.exec(code);
    if (match) found.push(`${match[0]}: ${why}`);
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
  it("allows AppShell.tsx only layout classes, token names and tokens", () => {
    const shell = shellSources.find(({ file }) => file === "AppShell.tsx");
    expect(shell).toBeDefined();
    expect(lookViolations(shell?.source ?? "")).toEqual([]);
  });

  it("reads the shell's own tokens from tokens.css", () => {
    const shell = shellSources.find(({ file }) => file === "AppShell.tsx");
    const used = new Set(
      [
        ...(shell?.source ?? "").matchAll(/\((?:[a-z-]+:)?(--shell-[\w-]+)\)/g),
      ].map(([, name]) => name),
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

// The check proved both ways, so a list that allows everything can't pass.
describe("the look check", () => {
  it.each([
    // Tailwind's own scales, which the shell takes from tokens instead.
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
    "border-b",
    "shadow-md",
    "bg-chrome/80",
    "-mt-4",
    // Families the blacklist never named (P-83).
    "scale-95",
    "duration-150",
    "blur-sm",
    "aspect-video",
    // And one nobody has named, kept, as D-084's gate test keeps
    // env-nobody-has-named-2031: whatever Tailwind adds next fails too.
    "quux-nobody-has-named-2031",
  ])("flags %s", (cls) => {
    expect(lookViolations(`<div className="${cls}" />`)).toHaveLength(1);
  });

  it.each([
    ["a number as an icon's size", "<Icon icon={Heart} size={19} />"],
    ["an inline style", "<div style={{ padding: 4 }} />"],
    ["a token that doesn't exist", '<div className="h-(--shell-nope)" />'],
    ["a class list in a variable", "<div className={classes} />"],
    ["a template with a value", "<div className={`flex ${classes}`} />"],
    ["a call other than cx", '<div className={clsx("flex")} />'],
    [
      "a condition that isn't a plain name",
      '<div className={cx("flex", count > 1 && "ml-auto")} />',
    ],
    ["a class list in an object", '<Link {...{ className: "flex" }} />'],
    ["a class prop of another name", "<Icon iconClassName={classes} />"],
  ])("flags %s", (_, source) => {
    expect(lookViolations(source)).toHaveLength(1);
  });

  it.each([
    "h-(--shell-header-height) px-(--shell-gutter) md:px-(--shell-gutter)",
    "text-micro text-title-1 bg-chrome text-chrome-accent border-chrome-line",
    "flex flex-1 flex-col items-center md:flex-none md:self-stretch",
    "fixed inset-x-0 bottom-0 top-0 z-10 md:pb-0 md:border-t-0",
    "border-b-(length:--shell-line) border-(length:--shell-line)",
    "mx-auto min-h-dvh max-w-(--shell-width) md:h-auto fill-current",
    "rounded-pill rounded-button shadow-1",
    "relative ml-auto before:absolute before:-inset-(--shell-pill-tap)",
  ])("allows %s", (classes) => {
    expect(lookViolations(`<div className="${classes}" />`)).toEqual([]);
  });

  it("reads cx() of strings, alone or behind a plain name", () => {
    expect(
      lookViolations(
        '<a className={cx("flex", current ? "text-chrome-accent" : "text-chrome-mute", current && "fill-current")} />',
      ),
    ).toEqual([]);
    expect(
      lookViolations('<a className={cx("flex", current && "px-5")} />'),
    ).toEqual(["px-5: not a layout class, a token's name or a token"]);
  });

  it("ignores comments, where tokens are named in prose", () => {
    expect(
      lookViolations(
        '/* `--shell-*` and "px-5" */\n// "text-sm"\nconst a = 1;',
      ),
    ).toEqual([]);
  });
});
