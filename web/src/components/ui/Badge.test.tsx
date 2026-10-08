import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge } from "./Badge";

describe("Badge", () => {
  it("shows its text, in ink by default", () => {
    render(<Badge>@ username</Badge>);

    const badge = screen.getByText("@ username");
    expect(badge).toHaveClass("bg-ink", "text-chrome-ink");
  });

  it("has a soft tone and a count tone", () => {
    render(
      <>
        <Badge tone="soft">Exact</Badge>
        <Badge tone="count">7</Badge>
      </>,
    );

    expect(screen.getByText("Exact")).toHaveClass(
      "bg-accent-soft",
      "text-accent",
    );
    expect(screen.getByText("7")).toHaveClass("bg-chrome-accent");
  });

  it("is read by its label when given one", () => {
    render(
      <Badge tone="count" label="7 people">
        7
      </Badge>,
    );

    expect(screen.getByRole("img", { name: "7 people" })).toHaveTextContent(
      "7",
    );
  });

  it("is never a button", () => {
    render(<Badge>New</Badge>);

    expect(screen.queryByRole("button")).toBeNull();
  });
});
