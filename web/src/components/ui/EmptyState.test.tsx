import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Inbox } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("shows a heading, body and an action that runs", async () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        icon={Inbox}
        title="Nobody matches that"
        body="Try clearing your search or filters."
        action={{ label: "Clear everything", onClick }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Nobody matches that" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Try clearing your search or filters."),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Clear everything" }),
    );
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("has no button without an action", () => {
    render(<EmptyState title="Nothing yet" />);

    expect(screen.queryByRole("button")).toBeNull();
  });
});
