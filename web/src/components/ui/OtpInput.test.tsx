import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { OtpInput } from "./OtpInput";

function Harness({ onComplete }: { onComplete?: (code: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <>
      <OtpInput
        label="Code"
        value={value}
        onChange={setValue}
        onComplete={onComplete}
      />
      <output>{value}</output>
    </>
  );
}

const box = (n: number) =>
  screen.getByRole("textbox", { name: `Digit ${n} of 6` });

describe("OtpInput", () => {
  it("is six labelled boxes in a named group, the first taking SMS autofill", () => {
    render(<Harness />);

    expect(screen.getByRole("group", { name: "Code" })).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")).toHaveLength(6);
    expect(box(1)).toHaveAttribute("autocomplete", "one-time-code");
    expect(box(2)).toHaveAttribute("autocomplete", "off");
    expect(box(1)).toHaveAttribute("inputmode", "numeric");
  });

  it("moves on as each digit is typed, and completes once", async () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);

    await userEvent.click(box(1));
    await userEvent.keyboard("123456");

    expect(screen.getByRole("status")).toHaveTextContent("123456");
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith("123456");
  });

  it("spreads a pasted code across the boxes, keeping only digits", async () => {
    const onComplete = vi.fn();
    render(<Harness onComplete={onComplete} />);

    await userEvent.click(box(1));
    await userEvent.paste("12 34-56");

    expect(screen.getByRole("status")).toHaveTextContent("123456");
    expect(onComplete).toHaveBeenCalledWith("123456");
  });

  it("spreads a code pasted into a box that already has a digit", async () => {
    render(<Harness />);

    await userEvent.click(box(1));
    await userEvent.keyboard("9");
    await userEvent.click(box(1));
    await userEvent.paste("123456");

    expect(screen.getByRole("status")).toHaveTextContent("123456");
  });

  it("ignores letters", async () => {
    render(<Harness />);

    await userEvent.click(box(1));
    await userEvent.keyboard("a1b");

    expect(screen.getByRole("status")).toHaveTextContent(/^1$/);
  });

  it("goes back a box on Backspace in an empty one", async () => {
    render(<Harness />);

    await userEvent.click(box(1));
    await userEvent.keyboard("12");
    await userEvent.keyboard("{Backspace}{Backspace}");

    expect(screen.getByRole("status")).toHaveTextContent(/^$/);
    expect(box(1)).toHaveFocus();
  });
});
