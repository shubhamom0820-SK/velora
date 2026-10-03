// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

// Both ways, like the fetch and zod bans: the Firebase SDK is refused
// everywhere but src/lib/firebase.ts (T-3.14). And the zod ban still holds
// beside it, since the two share one rule (eslint.config.mjs says why).
const eslint = new ESLint({ cwd: process.cwd() });

async function refused(filePath: string, code: string): Promise<number> {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? []).filter(
    (m) => m.ruleId === "no-restricted-imports",
  ).length;
}

describe(
  "the Firebase SDK is imported only from @/lib/firebase",
  { timeout: 30_000 },
  () => {
    it.each([
      [
        "src/components/onboarding/SignIn.tsx",
        'import { getAuth } from "firebase/auth";',
      ],
      [
        "src/lib/queries/onboarding.ts",
        'import { initializeApp } from "firebase/app";',
      ],
      ["src/app/(auth)/login/page.tsx", 'import firebase from "firebase";'],
      ["src/lib/zod.ts", 'import { getAuth } from "@firebase/auth";'],
    ])("refuses it in %s", async (filePath, code) => {
      expect(await refused(filePath, `${code}\nexport const x = 1;`)).toBe(1);
    });

    it("allows it inside src/lib/firebase.ts, and @/lib/firebase anywhere", async () => {
      expect(
        await refused(
          "src/lib/firebase.ts",
          'import { getAuth } from "firebase/auth";\nexport const x = getAuth;',
        ),
      ).toBe(0);
      expect(
        await refused(
          "src/components/onboarding/SignIn.tsx",
          'import { startFirebaseSignIn } from "@/lib/firebase";\nexport const x = startFirebaseSignIn;',
        ),
      ).toBe(0);
    });

    it("leaves the zod ban in force beside it, src/lib/firebase.ts included", async () => {
      const zod = 'import { z } from "zod";\nexport const s = z.string();';
      expect(await refused("src/components/onboarding/NameStep.tsx", zod)).toBe(
        1,
      );
      expect(await refused("src/lib/firebase.ts", zod)).toBe(1);
    });
  },
);
