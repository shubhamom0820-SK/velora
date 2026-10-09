import { describe, expect, it } from "vitest";

import { barsOf } from "./VoiceNote";

describe("a voice note's bars", () => {
  it("are decorative, but the same for a message every time", () => {
    expect(barsOf("m1")).toEqual(barsOf("m1"));
    expect(barsOf("m1")).toHaveLength(28);
    expect(barsOf("m1")).not.toEqual(barsOf("m2"));
  });
});
