import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Countdown } from "./Countdown";

const NOW = Date.parse("2026-10-09T12:00:00Z");
const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;

function at(leftMs: number) {
  const view = render(
    <Countdown expiresAt={new Date(NOW + leftMs).toISOString()} />,
  );
  const pill = screen.getByText(/left$|^Ran out$/);
  const seen = { text: pill.textContent, phase: pill.dataset.phase };
  view.unmount();
  return seen;
}

beforeEach(() => {
  vi.useFakeTimers({ now: NOW });
});

afterEach(() => {
  vi.useRealTimers();
});

// 08-DESIGN §8's pill: the numbers are the design's, written here as
// literals, so a change to the code's constants turns these red.
describe("Countdown", () => {
  it("says the minutes left on --accent-soft inside the hour", () => {
    expect(at(41 * MINUTE)).toEqual({ text: "41m left", phase: "running" });
  });

  it("rounds the minutes up, so it never says 0m while time is left", () => {
    expect(at(40 * MINUTE + 1)).toEqual({ text: "41m left", phase: "running" });
    expect(at(30 * SECOND)).toEqual({ text: "1m left", phase: "urgent" });
  });

  it("fills --accent under ten minutes, and not at ten", () => {
    expect(at(10 * MINUTE)).toEqual({ text: "10m left", phase: "running" });
    expect(at(10 * MINUTE - SECOND)).toEqual({
      text: "10m left",
      phase: "urgent",
    });
    expect(at(8 * MINUTE)).toEqual({ text: "8m left", phase: "urgent" });
  });

  it("says whole hours on --surface-2 past the hour: an Extended Thread", () => {
    expect(at(HOUR + SECOND)).toEqual({ text: "1h left", phase: "extended" });
    expect(at(22 * HOUR + 59 * MINUTE)).toEqual({
      text: "22h left",
      phase: "extended",
    });
  });

  it("reads a full hour as the hour, not as Extended", () => {
    expect(at(HOUR)).toEqual({ text: "1h left", phase: "running" });
    expect(at(HOUR - SECOND)).toEqual({ text: "1h left", phase: "running" });
  });

  it("says Ran out, never Expired, at the end and after it", () => {
    expect(at(0)).toEqual({ text: "Ran out", phase: "out" });
    expect(at(-5 * MINUTE)).toEqual({ text: "Ran out", phase: "out" });
  });

  it("moves with the shared ticker, and runs out on time", () => {
    render(
      <Countdown expiresAt={new Date(NOW + 41 * MINUTE + 1).toISOString()} />,
    );
    expect(screen.getByText("42m left")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(SECOND));
    expect(screen.getByText("41m left")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(41 * MINUTE));
    expect(screen.getByText("Ran out")).toBeInTheDocument();
  });
});
