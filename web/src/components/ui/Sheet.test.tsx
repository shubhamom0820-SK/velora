import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

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
});
