// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

// Both ways, like the Firebase ban: the Sentry SDK is refused everywhere but
// src/lib/sentry.ts and its own test (T-9.12), so nothing can send an event
// that skips its scrubber, or load the SDK into a build that doesn't report.
const eslint = new ESLint({ cwd: process.cwd() });

async function refused(filePath: string, code: string): Promise<number> {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? []).filter(
    (m) => m.ruleId === "no-restricted-imports",
  ).length;
}

describe(
  "the Sentry SDK is imported only from @/lib/sentry",
  { timeout: 30_000 },
  () => {
    it.each([
      [
        "src/instrumentation-client.ts",
        'import * as Sentry from "@sentry/nextjs";',
      ],
      ["src/instrumentation.ts", 'import { init } from "@sentry/nextjs";'],
      [
        "src/components/shell/AppShell.tsx",
        'import { captureException } from "@sentry/react";',
      ],
      ["src/lib/api.ts", 'import { captureException } from "@sentry/browser";'],
      ["src/lib/firebase.ts", 'import { init } from "@sentry/nextjs";'],
      ["src/lib/zod.ts", 'import { init } from "@sentry/core";'],
    ])("refuses it in %s", async (filePath, code) => {
      expect(await refused(filePath, `${code}\nexport const x = 1;`)).toBe(1);
    });

    it("allows it inside src/lib/sentry.ts, and @/lib/sentry anywhere", async () => {
      expect(
        await refused(
          "src/lib/sentry.ts",
          'import * as Sentry from "@sentry/nextjs";\nexport const x = Sentry;',
        ),
      ).toBe(0);
      expect(
        await refused(
          "src/instrumentation.ts",
          'import { startSentry } from "@/lib/sentry";\nexport const x = startSentry;',
        ),
      ).toBe(0);
    });

    it("leaves the zod and Firebase bans in force in src/lib/sentry.ts", async () => {
      expect(
        await refused(
          "src/lib/sentry.ts",
          'import { z } from "zod";\nexport const s = z;',
        ),
      ).toBe(1);
      expect(
        await refused(
          "src/lib/sentry.ts",
          'import { getAuth } from "firebase/auth";\nexport const x = getAuth;',
        ),
      ).toBe(1);
    });
  },
);
