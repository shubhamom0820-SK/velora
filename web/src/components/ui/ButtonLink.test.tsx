import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./Button";
import { buttonClasses } from "./buttonClasses";
import { ButtonLink } from "./ButtonLink";

describe("ButtonLink", () => {
  it("is a link named by its text, going to its href", () => {
    render(<ButtonLink href="/login">Get started</ButtonLink>);

    expect(screen.getByRole("link", { name: "Get started" })).toHaveAttribute(
      "href",
      "/login",
    );
  });

  it.each([
    ["primary", "md"],
    ["primary", "sm"],
    ["ghost", "md"],
    ["danger", "sm"],
    ["chrome", "md"],
  ] as const)("looks like a %s %s Button", (variant, size) => {
    render(
      <>
        <Button variant={variant} size={size}>
          As a button
        </Button>
        <ButtonLink href="/x" variant={variant} size={size}>
          As a link
        </ButtonLink>
      </>,
    );
    const shared = buttonClasses({ variant, size }).split(" ");

    expect(screen.getByRole("button")).toHaveClass(...shared);
    expect(screen.getByRole("link")).toHaveClass(...shared);
  });

  it("keeps a layout class from its caller", () => {
    render(
      <ButtonLink href="/x" className="mt-8">
        Join
      </ButtonLink>,
    );

    expect(screen.getByRole("link")).toHaveClass("mt-8", "rounded-button");
  });
});
