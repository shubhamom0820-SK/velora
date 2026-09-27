import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/ToastProvider";

import DevUiPage from "./page";

describe("/dev/ui", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(["production", "test"])("is not found when NODE_ENV is %s", (env) => {
    vi.stubEnv("NODE_ENV", env);

    expect(() => DevUiPage()).toThrow("NEXT_HTTP_ERROR_FALLBACK;404");
  });

  it("shows every primitive under next dev", () => {
    vi.stubEnv("NODE_ENV", "development");

    render(<ToastProvider>{DevUiPage()}</ToastProvider>);

    expect(
      screen.getByRole("heading", { level: 1, name: "UI primitives" }),
    ).toBeInTheDocument();
    for (const section of [
      "Button",
      "Chip",
      "Field",
      "TextArea",
      "Toggle",
      "Avatar",
      "Icon",
      "Spinner and Skeleton",
      "EmptyState and ErrorState",
      "Toast",
      "Sheet",
    ]) {
      expect(
        screen.getByRole("heading", { level: 2, name: section }),
      ).toBeInTheDocument();
    }
  });
});
