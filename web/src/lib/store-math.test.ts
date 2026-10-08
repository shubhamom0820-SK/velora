import { describe, expect, it } from "vitest";

import { bestValue, perThread, perVela, rupees } from "./store-math";

// D-099's four packs, as `GET /packs` sends them.
const PACKS = [
  { id: "p30", credits: 30, price_paise: 150_000 },
  { id: "p100", credits: 100, price_paise: 450_000 },
  { id: "p250", credits: 250, price_paise: 600_000 },
  { id: "p450", credits: 450, price_paise: 1_000_000 },
];

describe("the store's numbers, from the rows (T-8.7)", () => {
  it("prices in rupees, Indian grouping", () => {
    expect(rupees(150_000)).toBe("₹1,500");
    expect(rupees(1_000_000)).toBe("₹10,000");
  });

  it("D-099's per-Vela column", () => {
    expect(PACKS.map(perVela)).toEqual(["₹50", "₹45", "₹24", "₹22.22"]);
  });

  it("D-099's per-Thread column, at the Thread's price from /prices", () => {
    expect(PACKS.map((pack) => perThread(pack, 5))).toEqual([
      "₹250",
      "₹225",
      "₹120",
      "₹111",
    ]);
  });

  it("follows /prices, never a 5 of its own", () => {
    expect(perThread(PACKS[0]!, 2)).toBe("₹100");
  });
});

describe('"Best value" is the cheapest Vela, worked out, never named (D-760)', () => {
  it("is the ₹10,000 pack today", () => {
    expect(bestValue(PACKS)).toBe("p450");
  });

  it("moves when the rows do", () => {
    const repriced = PACKS.map((pack) =>
      pack.id === "p250" ? { ...pack, price_paise: 400_000 } : pack,
    );
    expect(bestValue(repriced)).toBe("p250");
  });

  it("doesn't depend on the order the rows come in", () => {
    expect(bestValue([...PACKS].reverse())).toBe("p450");
  });

  it("is none when two packs tie: neither is the best", () => {
    expect(
      bestValue([
        { id: "a", credits: 10, price_paise: 50_000 },
        { id: "b", credits: 20, price_paise: 100_000 },
      ]),
    ).toBeNull();
  });

  it("is none with one pack or none: nothing to compare", () => {
    expect(bestValue([PACKS[0]!])).toBeNull();
    expect(bestValue([])).toBeNull();
  });
});
