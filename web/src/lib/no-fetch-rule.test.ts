// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

// Proves eslint.config.mjs's fetch ban both ways (CLAUDE.md rule 14): it flags
// fetch outside src/lib, and leaves src/lib and look-alikes alone. Loading the
// Next.js ESLint config takes a few seconds, hence the timeout.
const eslint = new ESLint({ cwd: process.cwd() });

async function banned(filePath: string, code: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? [])
    .filter((m) => m.ruleId?.startsWith("no-restricted-"))
    .map((m) => m.ruleId ?? "");
}

describe("the fetch ban", { timeout: 30_000 }, () => {
  it.each([
    ["src/components/feed/Feed.tsx", "export const load = () => fetch('/x');"],
    [
      "src/app/(app)/discover/page.tsx",
      "export const load = () => window.fetch('/x');",
    ],
    [
      "src/app/admin/page.tsx",
      "export const load = () => globalThis.fetch('/x');",
    ],
    ["src/store/session.ts", "export const load = () => self.fetch('/x');"],
  ])("flags fetch in %s", async (filePath, code) => {
    expect(await banned(filePath, code)).toHaveLength(1);
  });

  it("allows fetch inside src/lib", async () => {
    expect(
      await banned("src/lib/api.ts", "export const load = () => fetch('/x');"),
    ).toEqual([]);
  });

  it("allows naming fetch, as tests do to stub it", async () => {
    expect(
      await banned(
        "src/components/ui/Button.test.tsx",
        "declare const vi: { stubGlobal(n: string, v: unknown): void };\nvi.stubGlobal('fetch', () => {});",
      ),
    ).toEqual([]);
  });

  it("allows a local binding called fetch", async () => {
    expect(
      await banned(
        "src/components/x.ts",
        "const fetch = (n: number) => n;\nexport const y = fetch(1);",
      ),
    ).toEqual([]);
  });
});
