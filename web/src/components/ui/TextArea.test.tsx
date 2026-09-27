import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import { TextArea } from "./TextArea";

describe("TextArea", () => {
  it("counts what is typed, up to its limit", async () => {
    render(<TextArea label="About you" maxLength={10} />);
    const box = screen.getByRole("textbox", { name: "About you" });
    expect(box).toHaveAccessibleDescription(
      t("ui.counter", { count: 0, max: 10 }),
    );

    await userEvent.type(box, "Filter coffee");

    expect(box).toHaveValue("Filter cof");
    expect(box).toHaveAccessibleDescription(
      t("ui.counter", { count: 10, max: 10 }),
    );
  });

  it("counts a starting value", () => {
    render(<TextArea label="About you" maxLength={300} defaultValue="Hi" />);

    expect(
      screen.getByText(t("ui.counter", { count: 2, max: 300 })),
    ).toBeInTheDocument();
  });

  it("shows no counter without a limit", () => {
    render(<TextArea label="Details" />);

    expect(
      screen.getByRole("textbox", { name: "Details" }),
    ).not.toHaveAttribute("aria-describedby");
  });
});
