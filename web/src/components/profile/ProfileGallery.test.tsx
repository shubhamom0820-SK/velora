import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";

import { ProfileGallery } from "./ProfileGallery";

describe("ProfileGallery's keyboard (T-9.11)", () => {
  it("makes more than one photo a named Tab stop, every photo inside it", async () => {
    render(<ProfileGallery urls={["https://p.test/1", "https://p.test/2"]} />);

    await userEvent.tab();
    const gallery = screen.getByRole("region", { name: t("profile.photos") });
    expect(gallery).toHaveFocus();
    expect(
      screen.getAllByRole("img").every((img) => gallery.contains(img)),
    ).toBe(true);
  });

  it("leaves one photo out of the Tab order: there is nothing to scroll to", () => {
    render(<ProfileGallery urls={["https://p.test/1"]} />);

    expect(screen.queryByRole("region")).not.toBeInTheDocument();
    expect(screen.getByRole("img").parentElement).not.toHaveAttribute(
      "tabindex",
    );
  });
});
