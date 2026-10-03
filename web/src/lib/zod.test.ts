// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

import { z } from "./zod";

describe("zod never compiles its parsers (T-3.11)", () => {
  it("is jitless, so it never probes new Function under the CSP", () => {
    expect(z.config().jitless).toBe(true);
  });
});

// Both ways, like the fetch ban: zod's own import is refused everywhere but
// src/lib/zod.ts, where the setting lives.
const eslint = new ESLint({ cwd: process.cwd() });

async function refused(filePath: string, code: string): Promise<number> {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? []).filter(
    (m) => m.ruleId === "no-restricted-imports",
  ).length;
}

describe("zod is imported only from @/lib/zod", { timeout: 30_000 }, () => {
  it.each([
    "src/components/onboarding/NameStep.tsx",
    "src/lib/queries/onboarding.ts",
    "src/app/(auth)/login/page.tsx",
  ])("refuses zod itself in %s", async (filePath) => {
    expect(
      await refused(
        filePath,
        'import { z } from "zod";\nexport const s = z.string();',
      ),
    ).toBe(1);
  });

  it("allows @/lib/zod, and zod inside it", async () => {
    expect(
      await refused(
        "src/components/onboarding/NameStep.tsx",
        'import { z } from "@/lib/zod";\nexport const s = z.string();',
      ),
    ).toBe(0);
    expect(
      await refused(
        "src/lib/zod.ts",
        'import { z } from "zod";\nexport { z };',
      ),
    ).toBe(0);
  });
});
