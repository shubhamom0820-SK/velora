import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import { Avatar } from "./Avatar";

describe("Avatar", () => {
  it("is an image named after the person, showing a photo", () => {
    const { container } = render(
      <Avatar name="Ananya" src="https://img.example/a.jpg" />,
    );

    expect(screen.getByRole("img", { name: "Ananya" })).toBeInTheDocument();
    expect(container.querySelector("img")).toHaveAttribute(
      "src",
      "https://img.example/a.jpg",
    );
  });

  it("falls back to the initial without a photo", () => {
    const { container } = render(<Avatar name="meera" />);

    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("img", { name: "meera" })).toHaveTextContent("M");
  });

  it("names its online and verified states", () => {
    render(<Avatar name="Kabir" online verified />);

    expect(
      screen.getByRole("img", {
        name: `Kabir, ${t("ui.online")}, ${t("ui.verified")}`,
      }),
    ).toBeInTheDocument();
  });
});
