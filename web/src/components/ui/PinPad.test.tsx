import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { PinPad } from "./PinPad";

function Harness({ onComplete }: { onComplete: (pin: string) => void }) {
  const [value, setValue] = useState("");
  return <PinPad value={value} onChange={setValue} onComplete={onComplete} />;
}

describe("PinPad", () => {
  it("has ten digits and a labelled delete, and shows how many are in", async () => {
    render(<Harness onComplete={() => {}} />);

    for (const digit of "0123456789") {
      expect(screen.getByRole("button", { name: digit })).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "0 of 4 digits entered",
    );

    await userEvent.click(screen.getByRole("button", { name: "4" }));
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "1 of 4 digits entered",
    );
  });

  it("completes once, with the four digits, and takes no fifth", async () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);

    for (const digit of "48295") {
      await userEvent.click(screen.getByRole("button", { name: digit }));
    }

    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith("4829");
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "4 of 4 digits entered",
    );
  });

  it("deletes the last digit", async () => {
    render(<Harness onComplete={() => {}} />);

    await userEvent.click(screen.getByRole("button", { name: "1" }));
    await userEvent.click(screen.getByRole("button", { name: "2" }));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(screen.getByRole("img")).toHaveAccessibleName(
      "1 of 4 digits entered",
    );
  });

  it("takes a physical keyboard's digits and Backspace", async () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);

    await userEvent.keyboard("12{Backspace}345");

    expect(onComplete).toHaveBeenCalledWith("1345");
  });

  it("ignores everything while disabled", async () => {
    const onChange = vi.fn();
    render(
      <PinPad value="" onChange={onChange} onComplete={() => {}} disabled />,
    );

    await userEvent.click(screen.getByRole("button", { name: "1" }));
    await userEvent.keyboard("2");

    expect(onChange).not.toHaveBeenCalled();
  });
});
