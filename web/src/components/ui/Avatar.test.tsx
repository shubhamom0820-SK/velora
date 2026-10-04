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

  it("marks a matched selfie with a face, never a shield (D-262)", () => {
    // A shield reads as a security guarantee; the words beside it say only
    // that a selfie matched photos.
    const { container } = render(<Avatar name="Kabir" verified />);

    expect(container.querySelector("svg.lucide-scan-face")).not.toBeNull();
    expect(container.querySelector("svg.lucide-shield")).toBeNull();
  });

  it("names its online and selfie-matched states", () => {
    render(<Avatar name="Kabir" online verified />);

    expect(
      screen.getByRole("img", {
        name: `Kabir, ${t("ui.online")}, ${t("ui.selfieMatched")}`,
      }),
    ).toBeInTheDocument();
  });
});
