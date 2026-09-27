import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Skeleton } from "./Skeleton";

describe("Skeleton", () => {
  it.each(["line", "card", "avatar"] as const)(
    "renders a %s hidden from screen readers",
    (variant) => {
      const { container } = render(<Skeleton variant={variant} />);

      const shape = container.firstElementChild;
      expect(shape).toBeInTheDocument();
      expect(shape).toHaveAttribute("aria-hidden", "true");
    },
  );
});
