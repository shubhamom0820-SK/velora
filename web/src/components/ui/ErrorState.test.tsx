import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";

import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("is an alert with a default title, and Try again retries", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent(t("ui.errorTitle"));

    await userEvent.click(screen.getByRole("button", { name: t("ui.retry") }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("takes its own title and body, and has no button without onRetry", () => {
    render(<ErrorState title="Chats didn't load" body="Check your signal." />);

    expect(
      screen.getByRole("heading", { name: "Chats didn't load" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Check your signal.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
