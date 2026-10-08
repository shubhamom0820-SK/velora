import { describe, expect, it } from "vitest";

import { searchQueryOf } from "./searchQuery";

describe("searchQueryOf: the API's own rules (D-540)", () => {
  it.each([
    ["", { kind: "empty" }],
    ["   ", { kind: "empty" }],
    ["@", { kind: "empty" }],
    ["@Priya", { kind: "username", q: "@priya" }],
    ["  @simran_k.2 ", { kind: "username", q: "@simran_k.2" }],
    ["@priya!", { kind: "badUsername" }],
    ["@pri ya", { kind: "badUsername" }],
    ["@" + "a".repeat(21), { kind: "badUsername" }],
    ["@" + "a".repeat(20), { kind: "username", q: "@" + "a".repeat(20) }],
    ["s", { kind: "tooShort" }],
    [" s ", { kind: "tooShort" }],
    ["si", { kind: "text", q: "si" }],
    [" Phagwara ", { kind: "text", q: "Phagwara" }],
  ])("%j is %j", (raw, want) => {
    expect(searchQueryOf(raw)).toEqual(want);
  });
});
