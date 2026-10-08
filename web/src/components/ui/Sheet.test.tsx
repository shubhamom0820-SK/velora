import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { resetSession, useSession } from "@/store/session";

import { Sheet } from "./Sheet";

function Harness({ onClose }: { onClose: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Block</button>
      <Sheet
        open={open}
        onClose={() => {
          onClose();
          setOpen(false);
        }}
        title="Block Ananya?"
        footer={<button>Confirm</button>}
      >
        <input aria-label="Reason" />
      </Sheet>
    </>
  );
}

async function openSheet() {
  const onClose = vi.fn();
  render(<Harness onClose={onClose} />);
  await userEvent.click(screen.getByRole("button", { name: "Block" }));
  return { onClose, dialog: screen.getByRole("dialog") };
}

afterEach(() => {
  resetSession();
});

describe("Sheet", () => {
  it("renders nothing while closed", () => {
    render(<Harness onClose={() => {}} />);

    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens as a modal dialog named by its title, holding focus", async () => {
    const { dialog } = await openSheet();

    expect(dialog).toHaveAccessibleName("Block Ananya?");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveFocus();
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("keeps Tab and Shift+Tab inside, wrapping at both ends", async () => {
    await openSheet();
    const close = screen.getByRole("button", { name: t("ui.close") });
    const reason = screen.getByRole("textbox", { name: "Reason" });
    const confirm = screen.getByRole("button", { name: "Confirm" });

    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.tab();
    expect(reason).toHaveFocus();
    await userEvent.tab();
    expect(confirm).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();

    await userEvent.tab({ shift: true });
    expect(confirm).toHaveFocus();
  });

  it("closes on Esc and gives focus back to the opener", async () => {
    const { onClose } = await openSheet();

    await userEvent.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Block" })).toHaveFocus();
    expect(document.body.style.overflow).toBe("");
  });

  it("closes from ✕ and from the backdrop, but not from a click inside", async () => {
    const { onClose, dialog } = await openSheet();

    await userEvent.click(screen.getByRole("textbox", { name: "Reason" }));
    expect(onClose).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: t("ui.close") }));
    expect(onClose).toHaveBeenCalledOnce();

    await userEvent.click(screen.getByRole("button", { name: "Block" }));
    const backdrop = screen.getByRole("dialog").previousElementSibling;
    expect(backdrop).not.toBe(dialog);
    await userEvent.click(backdrop as Element);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("is out of reach while the PIN lock is up, and keeps what was written (P-220)", async () => {
    const { dialog } = await openSheet();
    const reason = screen.getByRole("textbox", { name: "Reason" });
    await userEvent.type(reason, "Rude in chat");
    expect(dialog.closest("[inert]")).toBeNull();

    act(() => useSession.getState().setLocked(true));
    expect(dialog.closest("[inert]")).not.toBeNull();
    // jsdom doesn't act on `inert`, nor Testing Library's role queries; a
    // browser takes it out of focus, clicks and the accessibility tree, as it
    // does the page behind the lock (SignedInFrame).

    act(() => useSession.getState().setLocked(false));
    expect(screen.getByRole("dialog")).toBe(dialog);
    expect(dialog.closest("[inert]")).toBeNull();
    expect(reason).toHaveValue("Rude in chat");
  });
});

describe("Sheet, chrome (the match sheet, 08-DESIGN §8)", () => {
  it("draws its lead above its title, still named by the title, and still closes", async () => {
    const onClose = vi.fn();
    render(
      <Sheet
        open
        onClose={onClose}
        title="You and Priya liked each other"
        tone="chrome"
        lead={<span data-testid="pair">P · S</span>}
      >
        <p>body</p>
      </Sheet>,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAccessibleName("You and Priya liked each other");
    expect(dialog).toHaveClass("bg-chrome");
    const heading = screen.getByRole("heading", { level: 2 });
    expect(
      screen.getByTestId("pair").compareDocumentPosition(heading) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: t("ui.close") }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
