import { render, screen } from "@testing-library/react";
import { connection } from "next/server";
import { describe, expect, it, vi } from "vitest";

import NotFound from "./not-found";

// A brand that is neither the prototype's nor ours (CLAUDE.md rule 17).
vi.mock("@/lib/app", () => ({ APP_NAME: "Zephyrine" }));
// No request here; the page asks for one so that it is never prerendered.
vi.mock("next/server", () => ({ connection: vi.fn(async () => undefined) }));

describe("the 404 page (P-445, D-980)", () => {
  it("says the page isn't here and links home", async () => {
    render(await NotFound());

    expect(
      screen.getByRole("heading", { name: "This page isn't here" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("The link may be old or mistyped."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to Zephyrine" }),
    ).toHaveAttribute("href", "/");
  });

  it("renders per request, so a nonce route's 404 carries its nonce", async () => {
    vi.mocked(connection).mockClear();

    await NotFound();

    expect(connection).toHaveBeenCalledOnce();
  });

  it("sets no inline style, which neither CSP allows", async () => {
    const { container } = render(await NotFound());

    expect(container.querySelectorAll("[style], style")).toHaveLength(0);
  });
});
