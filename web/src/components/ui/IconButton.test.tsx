import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Heart, X } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { IconButton } from "./IconButton";
import { PriceTag } from "./PriceTag";

describe("IconButton", () => {
  it("is a button named by its label, never by its icon", async () => {
    const onClick = vi.fn();
    render(<IconButton icon={Heart} label="Like" onClick={onClick} />);

    const button = screen.getByRole("button", { name: "Like" });
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("carries a badge that adds nothing to its name", () => {
    render(
      <IconButton
        icon={Heart}
        label="Super Like, 5 Velas"
        badge={<PriceTag credits={5} />}
      />,
    );

    const button = screen.getByRole("button", { name: "Super Like, 5 Velas" });
    expect(button).toHaveTextContent("5");
  });

  it("can't be pressed while disabled", async () => {
    const onClick = vi.fn();
    render(<IconButton icon={X} label="Pass" disabled onClick={onClick} />);

    await userEvent.click(screen.getByRole("button", { name: "Pass" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});
