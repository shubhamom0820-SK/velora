// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

// Proves eslint.config.mjs's fetch ban both ways (CLAUDE.md rule 14): it flags
// fetch, since T-4.6 XMLHttpRequest and since T-7.12 WebSocket, outside src/lib, and leaves src/lib
// and look-alikes alone. Loading the Next.js ESLint config takes a few seconds,
// hence the timeout.
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

  it.each([
    [
      "src/components/onboarding/PhotosStep.tsx",
      "export const put = () => new XMLHttpRequest();",
    ],
    [
      "src/app/(auth)/onboarding/[step]/page.tsx",
      "export const put = () => new window.XMLHttpRequest();",
    ],
    [
      "src/components/x.tsx",
      "export const put = () => new globalThis.XMLHttpRequest();",
    ],
    ["src/store/x.ts", "export const put = () => new self.XMLHttpRequest();"],
  ])("flags XMLHttpRequest in %s (T-4.6)", async (filePath, code) => {
    expect(await banned(filePath, code)).toHaveLength(1);
  });

  it("allows XMLHttpRequest inside src/lib, where the upload is", async () => {
    expect(
      await banned(
        "src/lib/upload.ts",
        "export const put = () => new XMLHttpRequest();",
      ),
    ).toEqual([]);
  });

  it.each([
    [
      "src/components/conversation/Composer.tsx",
      "export const open = () => new WebSocket('wss://x/ws');",
    ],
    [
      "src/app/(app)/chats/page.tsx",
      "export const open = () => new window.WebSocket('wss://x/ws');",
    ],
    [
      "src/components/x.tsx",
      "export const open = () => new globalThis.WebSocket('wss://x/ws');",
    ],
    [
      "src/store/x.ts",
      "export const open = () => new self.WebSocket('wss://x/ws');",
    ],
  ])("flags WebSocket in %s (T-7.12)", async (filePath, code) => {
    expect(await banned(filePath, code)).toHaveLength(1);
  });

  it("allows WebSocket inside src/lib, where the socket is", async () => {
    expect(
      await banned(
        "src/lib/ws.ts",
        "export const open = () => new WebSocket('wss://x/ws');",
      ),
    ).toEqual([]);
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
