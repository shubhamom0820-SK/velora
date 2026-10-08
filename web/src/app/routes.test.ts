// @vitest-environment node
import { readdirSync } from "node:fs";
import { join } from "node:path";

import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";
import { describe, expect, it } from "vitest";

import { nextConfig } from "../../next.config";

const APP = join(process.cwd(), "src", "app");

function folders(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .flatMap((entry) => {
      const path = join(dir, entry.name);
      return [path, ...folders(path)];
    });
}

describe("routes (D-068, T-6.8)", () => {
  it("has no route segment beginning with @, which Next reads as a parallel route's slot", () => {
    const at = folders(APP).filter((path) =>
      path.split("/").pop()?.startsWith("@"),
    );

    expect(at).toEqual([]);
  });

  it("serves /@username through the internal /share route, a username only", async () => {
    const rewrites = await nextConfig.rewrites?.();
    expect(rewrites).toEqual([
      {
        source: "/@:username([A-Za-z0-9._]{4,20})",
        destination: "/share/:username",
      },
    ]);
    const source = (rewrites as { source: string }[])[0]?.source ?? "";
    const match = getPathMatch(source, { strict: true });

    expect(match("/@priya")).toEqual({ username: "priya" });
    expect(match("/@Simran.K")).toEqual({ username: "Simran.K" });
    for (const path of [
      "/@ab",
      "/@a!bcd",
      "/@priya/x",
      "/priya",
      "/@" + "a".repeat(21),
    ]) {
      expect(match(path), path).toBe(false);
    }
  });
});
