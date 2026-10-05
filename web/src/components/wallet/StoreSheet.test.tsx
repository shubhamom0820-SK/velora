import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { resetSession, useSession } from "@/store/session";
import { useStoreSheet } from "@/store/store-sheet";

import { StoreSheet } from "./StoreSheet";

vi.mock("@/lib/app", () => ({ APP_NAME: "Zephyrine" }));

const open = () => act(() => useStoreSheet.getState().show());

beforeEach(() => {
  useStoreSheet.setState({ open: false });
});

afterEach(() => {
  resetSession();
});

describe("the store sheet, until T-8.7 (T-5.5)", () => {
  it("is shut until something opens it", () => {
    render(<StoreSheet />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("says plainly that buying hasn't started, with no promise of when", () => {
    render(<StoreSheet />);
    open();

    const sheet = screen.getByRole("dialog", { name: t("wallet.store.title") });
    expect(sheet).toHaveTextContent(
      t("wallet.store.body", { app: "Zephyrine" }),
    );
    expect(sheet).not.toHaveTextContent(/soon|shortly|stay tuned|notify/i);
  });

  it("closes with its ✕", async () => {
    render(<StoreSheet />);
    open();

    await userEvent.click(screen.getByRole("button", { name: t("ui.close") }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(useStoreSheet.getState().open).toBe(false);
  });

  it("closes when the PIN lock goes up, and stays shut after unlocking", () => {
    render(<StoreSheet />);
    open();

    act(() => useSession.getState().setLocked(true));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(useStoreSheet.getState().open).toBe(false);

    act(() => useSession.getState().setLocked(false));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes when the app's routes go away, so a sign-out doesn't carry it over", () => {
    const { unmount } = render(<StoreSheet />);
    open();

    unmount();

    expect(useStoreSheet.getState().open).toBe(false);
  });
});
