import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Field } from "./Field";

describe("Field", () => {
  it("is a textbox found by its label that takes typing", async () => {
    render(<Field label="First name" />);
    const input = screen.getByRole("textbox", { name: "First name" });

    await userEvent.type(input, "Ananya");

    expect(input).toHaveValue("Ananya");
    expect(input).not.toHaveAttribute("aria-invalid");
  });

  it("is described by its helper", () => {
    render(<Field label="Username" helper="Letters, numbers and dots" />);

    expect(
      screen.getByRole("textbox", { name: "Username" }),
    ).toHaveAccessibleDescription("Letters, numbers and dots");
  });

  it("is invalid and described by its error, which replaces the helper", () => {
    render(
      <Field
        label="Username"
        helper="Letters, numbers and dots"
        error="That username is taken"
      />,
    );
    const input = screen.getByRole("textbox", { name: "Username" });

    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("That username is taken");
    expect(screen.queryByText("Letters, numbers and dots")).toBeNull();
  });
});
