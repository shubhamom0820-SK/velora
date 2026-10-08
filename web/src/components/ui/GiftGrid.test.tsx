import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { GiftGrid, type GiftTile } from "./GiftGrid";

const GIFTS: GiftTile[] = [
  { id: "coffee", label: "Coffee", asset: "☕", price: "Free" },
  { id: "rose", label: "Rose", asset: "🌹", price: "10 Velas" },
];

describe("GiftGrid", () => {
  it("names each gift with its price, and says the note", () => {
    render(
      <GiftGrid
        gifts={GIFTS}
        selected={null}
        onSelect={() => {}}
        note="3 free sends left this week"
      />,
    );

    expect(
      screen.getByRole("button", { name: "Coffee, Free" }),
    ).toHaveAttribute("aria-pressed", "false");
    expect(
      screen.getByRole("button", { name: "Rose, 10 Velas" }),
    ).toBeInTheDocument();
    expect(screen.getByText("3 free sends left this week")).toBeInTheDocument();
  });

  it("marks the chosen one and reports a tap", async () => {
    const onSelect = vi.fn();
    render(<GiftGrid gifts={GIFTS} selected="rose" onSelect={onSelect} />);

    expect(
      screen.getByRole("button", { name: "Rose, 10 Velas" }),
    ).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Coffee, Free" }));
    expect(onSelect).toHaveBeenCalledWith("coffee");
  });

  it("takes no tap while disabled", async () => {
    const onSelect = vi.fn();
    render(
      <GiftGrid gifts={GIFTS} selected={null} onSelect={onSelect} disabled />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Coffee, Free" }));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
