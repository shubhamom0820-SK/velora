import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { SharedProfileView } from "./SharedProfileView";

// A brand that is neither the prototype's nor ours (CLAUDE.md rule 17).
vi.mock("@/lib/app", () => ({ APP_NAME: "Zephyrine" }));

describe("/@username's page (T-6.8, D-544)", () => {
  it("shows her first name, age, city and main photo, and the way in", () => {
    const { container } = render(
      <SharedProfileView
        shared={{
          username: "noor_s",
          first_name: "Noor",
          age: 23,
          city: "Phagwara",
          main_photo_url: "https://cdn.test/p/1.jpg",
        }}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: t("profile.nameAge", { name: "Noor", age: 23 }),
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Phagwara")).toBeInTheDocument();
    // Decorative: her name is beside it.
    expect(container.querySelector("img")).toHaveAttribute(
      "src",
      "https://cdn.test/p/1.jpg",
    );
    expect(
      screen.getByRole("link", { name: t("share.join", { app: "Zephyrine" }) }),
    ).toHaveAttribute("href", "/login");
  });

  it("shows no age when she hides it", () => {
    render(
      <SharedProfileView
        shared={{
          username: "noor_s",
          first_name: "Noor",
          age: null,
          city: null,
          main_photo_url: null,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Noor" })).toBeInTheDocument();
  });

  it("says only that it isn't public when the API refused, nothing of hers", () => {
    render(<SharedProfileView shared={null} />);

    expect(
      screen.getByRole("heading", { name: t("share.unavailable") }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });
});
