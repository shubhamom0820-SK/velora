import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PriceTag } from "./PriceTag";

describe("PriceTag", () => {
  it("draws the number alone, hidden from screen readers", () => {
    const { container } = render(<PriceTag credits={7} />);

    const tag = container.firstElementChild;
    expect(tag).toHaveTextContent(/^7$/);
    expect(tag).toHaveAttribute("aria-hidden", "true");
  });

  it("groups a large price the Indian way", () => {
    const { container } = render(<PriceTag credits={125000} />);

    expect(container.firstElementChild).toHaveTextContent("1,25,000");
  });
});
