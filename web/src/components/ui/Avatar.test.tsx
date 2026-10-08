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

  it("marks the badge with a tick in the accent, never a shield (D-393, D-262)", () => {
    // A tick reads as "verified" where the words may not say it: the founder
    // chose it knowing that (7 October 2026). A shield reads as a security
    // guarantee and stays rejected; the words say only that a selfie matched.
    const { container } = render(<Avatar name="Kabir" verified />);

    const tick = container.querySelector("svg.lucide-check");
    expect(tick).not.toBeNull();
    expect(tick?.parentElement).toHaveClass("text-accent");
    expect(container.querySelector("svg.lucide-shield")).toBeNull();
    expect(container.querySelector("svg.lucide-scan-face")).toBeNull();
  });

  it("names its online and badge states, the badge as 'Selfie matched'", () => {
    render(<Avatar name="Kabir" online verified />);

    expect(
      screen.getByRole("img", {
        name: `Kabir, ${t("ui.online")}, ${t("ui.selfieMatched")}`,
      }),
    ).toBeInTheDocument();
    expect(t("ui.selfieMatched")).toBe("Selfie matched");
  });
});
