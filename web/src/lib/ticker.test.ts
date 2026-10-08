import { act, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useNow } from "./ticker";

function Clock({ n }: { n: number }) {
  return createElement("span", { "data-testid": `clock-${n}` }, useNow());
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("the shared ticker (T-7.10)", () => {
  it("runs one 1 s interval for every reader, and stops when the last leaves", () => {
    vi.useFakeTimers({ now: 0 });
    const set = vi.spyOn(globalThis, "setInterval");
    const clear = vi.spyOn(globalThis, "clearInterval");
    const ticks = () => set.mock.calls.filter(([, ms]) => ms === 1000).length;

    const view = render(
      createElement(
        "div",
        null,
        [1, 2, 3, 4, 5].map((n) => createElement(Clock, { key: n, n })),
      ),
    );

    // Five readers, one interval: never one per row.
    expect(ticks()).toBe(1);
    act(() => vi.advanceTimersByTime(1000));
    for (const n of [1, 2, 3, 4, 5]) {
      expect(screen.getByTestId(`clock-${n}`)).toHaveTextContent("1000");
    }

    view.unmount();
    const timer = set.mock.results[0]?.value as unknown;
    expect(clear).toHaveBeenCalledWith(timer);

    // A later reader starts it again, once.
    render(createElement(Clock, { n: 6 }));
    expect(ticks()).toBe(2);
  });

  it("moves every reader together, a second at a time", () => {
    vi.useFakeTimers({ now: 5000 });
    render(
      createElement(
        "div",
        null,
        createElement(Clock, { n: 1 }),
        createElement(Clock, { n: 2 }),
      ),
    );
    expect(screen.getByTestId("clock-1")).toHaveTextContent("5000");

    act(() => vi.advanceTimersByTime(999));
    expect(screen.getByTestId("clock-1")).toHaveTextContent("5000");
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByTestId("clock-1")).toHaveTextContent("6000");
    expect(screen.getByTestId("clock-2")).toHaveTextContent("6000");
  });
});
