import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

describe("Button", () => {
  it("is a button named by its text that runs onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Open thread</Button>);

    await userEvent.click(screen.getByRole("button", { name: "Open thread" }));

    expect(onClick).toHaveBeenCalledOnce();
  });

  it("doesn't submit a form unless asked to", () => {
    render(<Button>Save</Button>);

    expect(screen.getByRole("button")).toHaveAttribute("type", "button");
  });

  it("ignores clicks while loading, but keeps its name and focus", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Pay
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Pay" });

    await userEvent.click(button);
    await userEvent.dblClick(button);

    expect(onClick).not.toHaveBeenCalled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toBeEnabled();
    expect(button).toHaveFocus();
  });

  it("doesn't submit its form while loading", async () => {
    const onSubmit = vi.fn((event: SubmitEvent) => event.preventDefault());
    render(
      <form onSubmit={(event) => onSubmit(event.nativeEvent as SubmitEvent)}>
        <Button type="submit" loading>
          Pay
        </Button>
      </form>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Pay" }));

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("ignores clicks when disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button variant="danger" disabled onClick={onClick}>
        Block
      </Button>,
    );

    await userEvent.click(screen.getByRole("button", { name: "Block" }));

    expect(onClick).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
