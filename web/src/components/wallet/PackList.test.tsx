import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import type { Pack } from "@/lib/queries/store";

import { PackList } from "./PackList";

/** D-099's four packs with D-231's first-purchase bonus, as `GET /packs` sends them. */
const D099_PACKS: Pack[] = [
  { id: "p30", credits: 30, price_paise: 150_000, bonus_credits: 6 },
  { id: "p100", credits: 100, price_paise: 450_000, bonus_credits: 20 },
  { id: "p250", credits: 250, price_paise: 600_000, bonus_credits: 50 },
  { id: "p450", credits: 450, price_paise: 1_000_000, bonus_credits: 90 },
];

const noBonus = (packs: Pack[]) =>
  packs.map((pack) => ({ ...pack, bonus_credits: 0 }));

function rows() {
  return within(screen.getByRole("list")).getAllByRole("button");
}

describe("the store's packs (T-8.7)", () => {
  it("shows each pack's Velas, its rate per Vela and per Thread, and its price", () => {
    render(
      <PackList
        packs={noBonus(D099_PACKS)}
        threadPrice={5}
        disabled={false}
        onBuy={vi.fn()}
      />,
    );

    expect(rows().map((row) => row.textContent)).toEqual([
      "30 Velas₹50 a Vela · ₹250 a Thread₹1,500",
      "100 Velas₹45 a Vela · ₹225 a Thread₹4,500",
      "250 Velas₹24 a Vela · ₹120 a Thread₹6,000",
      `450 Velas${t("wallet.store.bestValue")}₹22.22 a Vela · ₹111 a Thread₹10,000`,
    ]);
  });

  it('"Best value" is on the cheapest Vela alone, and nothing says "Most popular" (D-760)', () => {
    render(
      <PackList
        packs={D099_PACKS}
        threadPrice={5}
        disabled={false}
        onBuy={vi.fn()}
      />,
    );

    expect(screen.getAllByText(t("wallet.store.bestValue"))).toHaveLength(1);
    expect(rows()[3]).toHaveTextContent(t("wallet.store.bestValue"));
    expect(document.body).not.toHaveTextContent(/most popular|popular/i);
  });

  it("the first-purchase banner, and each pack's own bonus, while there is one", () => {
    render(
      <PackList
        packs={D099_PACKS}
        threadPrice={5}
        disabled={false}
        onBuy={vi.fn()}
      />,
    );

    expect(
      screen.getByText(t("wallet.store.firstPurchase")),
    ).toBeInTheDocument();
    expect(
      rows().map((row) => within(row).queryByText(/bonus/)?.textContent),
    ).toEqual(["+6 bonus", "+20 bonus", "+50 bonus", "+90 bonus"]);
  });

  it("no banner and no bonus once he has bought (the API's 0)", () => {
    render(
      <PackList
        packs={noBonus(D099_PACKS)}
        threadPrice={5}
        disabled={false}
        onBuy={vi.fn()}
      />,
    );

    expect(
      screen.queryByText(t("wallet.store.firstPurchase")),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/bonus/)).not.toBeInTheDocument();
  });

  it("without /prices, the rate per Vela alone, never a Thread priced from a guess", () => {
    render(
      <PackList
        packs={noBonus(D099_PACKS)}
        threadPrice={undefined}
        disabled={false}
        onBuy={vi.fn()}
      />,
    );

    expect(rows()[0]).toHaveTextContent("₹50 a Vela");
    expect(rows()[0]).not.toHaveTextContent("Thread");
  });

  it("a tap buys that pack; while an order is being made, no pack can be tapped", async () => {
    const onBuy = vi.fn();
    const { rerender } = render(
      <PackList
        packs={D099_PACKS}
        threadPrice={5}
        disabled={false}
        onBuy={onBuy}
      />,
    );

    await userEvent.click(rows()[1]!);
    expect(onBuy).toHaveBeenCalledWith(D099_PACKS[1]);

    rerender(
      <PackList packs={D099_PACKS} threadPrice={5} disabled onBuy={onBuy} />,
    );
    for (const row of rows()) expect(row).toBeDisabled();
  });
});
