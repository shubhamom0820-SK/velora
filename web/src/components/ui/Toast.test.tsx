import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, type ToastOptions } from "./ToastProvider";
import { useToast } from "./useToast";

function Trigger({ options }: { options: ToastOptions }) {
  const toast = useToast();
  return <button onClick={() => toast.show(options)}>Show</button>;
}

function renderWith(options: ToastOptions) {
  render(
    <ToastProvider>
      <Trigger options={options} />
    </ToastProvider>,
  );
}

describe("Toast", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("announces an info toast politely", async () => {
    renderWith({ message: "Cleared from your chats" });

    await userEvent.click(screen.getByRole("button", { name: "Show" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "Cleared from your chats",
    );
    expect(screen.getByRole("alert")).toBeEmptyDOMElement();
  });

  it("announces an error toast as an alert", async () => {
    renderWith({ message: "Payment failed", tone: "error" });

    await userEvent.click(screen.getByRole("button", { name: "Show" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Payment failed");
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("runs its action, then goes away", async () => {
    const undo = vi.fn();
    renderWith({
      message: "Cleared from your chats",
      action: { label: "Undo", onClick: undo },
    });
    await userEvent.click(screen.getByRole("button", { name: "Show" }));

    await userEvent.click(screen.getByRole("button", { name: "Undo" }));

    expect(undo).toHaveBeenCalledOnce();
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("goes away by itself after its duration", () => {
    vi.useFakeTimers();
    renderWith({ message: "Link copied", durationMs: 3000 });
    // A synchronous click: user-event's own delays would wait on the fake clock.
    fireEvent.click(screen.getByRole("button", { name: "Show" }));

    act(() => vi.advanceTimersByTime(2999));
    expect(screen.getByRole("status")).toHaveTextContent("Link copied");

    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });

  it("refuses to work outside a provider", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<Trigger options={{ message: "x" }} />)).toThrow(
      /ToastProvider/,
    );
  });
});
