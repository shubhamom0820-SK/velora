import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { CheckoutState } from "./CheckoutState";

const button = (name: string) => screen.getByRole("button", { name });

describe("the checkout's states (T-8.7)", () => {
  it("the stand-in: says no money moves, and pays or closes", async () => {
    const onPay = vi.fn();
    const onClose = vi.fn();
    render(<CheckoutState view="standin" onPay={onPay} onClose={onClose} />);

    expect(
      screen.getByText(t("wallet.store.standin.body")),
    ).toBeInTheDocument();
    await userEvent.click(button(t("wallet.store.standin.pay")));
    await userEvent.click(button(t("wallet.store.standin.close")));
    expect(onPay).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("confirming: a spinner named for what it waits on, and no button to pay again", () => {
    render(<CheckoutState view="confirming" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      t("wallet.store.confirming.title"),
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("didn't go through: Try again, another pack, or a claim", async () => {
    const onRetry = vi.fn();
    const onPacks = vi.fn();
    const onClaim = vi.fn();
    render(
      <CheckoutState
        view="notPaid"
        onRetry={onRetry}
        onPacks={onPacks}
        onClaim={onClaim}
      />,
    );

    expect(
      screen.getByText(t("wallet.store.notPaid.body")),
    ).toBeInTheDocument();
    // Never the prototype's "No money was taken": a UPI debit can still land.
    expect(document.body).not.toHaveTextContent(/no money was taken/i);
    await userEvent.click(button(t("wallet.store.notPaid.retry")));
    await userEvent.click(button(t("wallet.store.notPaid.packs")));
    await userEvent.click(button(t("wallet.store.claim.open")));
    expect([onRetry, onPacks, onClaim].map((f) => f.mock.calls.length)).toEqual(
      [1, 1, 1],
    );
  });

  it("still confirming: says not to pay again, and checks again, claims or closes", async () => {
    const onCheck = vi.fn();
    const onClaim = vi.fn();
    const onClose = vi.fn();
    render(
      <CheckoutState
        view="waiting"
        onCheck={onCheck}
        onClaim={onClaim}
        onClose={onClose}
      />,
    );

    expect(screen.getByText(t("wallet.store.waiting.body"))).toHaveTextContent(
      /no need to pay again/,
    );
    await userEvent.click(button(t("wallet.store.waiting.check")));
    await userEvent.click(button(t("wallet.store.claim.open")));
    await userEvent.click(button(t("wallet.store.close")));
    expect([onCheck, onClaim, onClose].map((f) => f.mock.calls.length)).toEqual(
      [1, 1, 1],
    );
  });
});
