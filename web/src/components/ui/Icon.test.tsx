import { render, screen } from "@testing-library/react";
import { Heart } from "lucide-react";
import { describe, expect, it } from "vitest";

import { Icon } from "./Icon";

describe("Icon", () => {
  it("is hidden from screen readers when decorative", () => {
    const { container } = render(<Icon icon={Heart} />);

    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("is an image named by its label", () => {
    render(<Icon icon={Heart} label="Liked" size={14} />);

    const svg = screen.getByRole("img", { name: "Liked" });
    expect(svg).toHaveAttribute("width", "14");
  });
});
