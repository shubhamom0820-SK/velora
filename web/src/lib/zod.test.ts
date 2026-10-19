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

describe("zod only through @/lib/zod(-mini)", { timeout: 30_000 }, () => {
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

  // Anchored, so a subpath can't slip past the setting (T-9.10).
  it.each(["zod/mini", "zod/v4", "zod/v4/core"])(
    "refuses %s outside the two modules",
    async (from) => {
      expect(
        await refused(
          "src/lib/ws.ts",
          `import { string } from "${from}";\nexport const s = string();`,
        ),
      ).toBe(1);
    },
  );

  it("allows @/lib/zod-mini, and zod/mini inside it", async () => {
    expect(
      await refused(
        "src/lib/ws.ts",
        'import { z } from "@/lib/zod-mini";\nexport const s = z.string();',
      ),
    ).toBe(0);
    expect(
      await refused(
        "src/lib/zod-mini.ts",
        'import { string } from "zod/mini";\nexport const s = string();',
      ),
    ).toBe(0);
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
