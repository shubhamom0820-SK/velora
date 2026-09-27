import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { Chip } from "./Chip";

function ToggleChip() {
  const [on, setOn] = useState(false);
  return (
    <Chip active={on} onClick={() => setOn(!on)}>
      Verified only
    </Chip>
  );
}

describe("Chip", () => {
  it("is a toggle button whose pressed state flips on click", async () => {
    render(<ToggleChip />);
    const chip = screen.getByRole("button", { name: "Verified only" });
    expect(chip).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(chip);

    expect(chip).toHaveAttribute("aria-pressed", "true");
  });

  it("is a plain button when it isn't a toggle", () => {
    render(<Chip onClick={() => {}}>For you</Chip>);

    expect(screen.getByRole("button", { name: "For you" })).not.toHaveAttribute(
      "aria-pressed",
    );
  });

  it("has a named remove button when removable", async () => {
    const onRemove = vi.fn();
    render(<Chip onRemove={onRemove}>Trekking</Chip>);

    await userEvent.click(
      screen.getByRole("button", {
        name: t("ui.remove", { label: "Trekking" }),
      }),
    );

    expect(onRemove).toHaveBeenCalledOnce();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });
});
