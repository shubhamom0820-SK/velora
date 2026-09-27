import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Toggle } from "./Toggle";

function Setting() {
  const [on, setOn] = useState(false);
  return (
    <Toggle
      label="New message"
      description="Only the name, never the text"
      checked={on}
      onChange={setOn}
    />
  );
}

describe("Toggle", () => {
  it("is a switch named by its label that flips on click and on Space", async () => {
    render(<Setting />);
    const toggle = screen.getByRole("switch", { name: "New message" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(toggle).toHaveAccessibleDescription("Only the name, never the text");

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");

    await userEvent.keyboard(" ");
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("doesn't change when disabled", async () => {
    const onChange = vi.fn();
    render(<Toggle label="Incognito" checked onChange={onChange} disabled />);

    await userEvent.click(screen.getByRole("switch", { name: "Incognito" }));

    expect(onChange).not.toHaveBeenCalled();
  });
});
