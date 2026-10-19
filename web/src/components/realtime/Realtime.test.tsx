import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/lib/queries/keys";
import { makeQueryClient } from "@/lib/queries/QueryProvider";
import type { RealtimeOptions } from "@/lib/ws";

import { Realtime } from "./Realtime";

const made = vi.hoisted(() => ({
  options: [] as RealtimeOptions[],
  start: vi.fn(),
  stop: vi.fn(),
  current: [] as unknown[],
}));
vi.mock("@/lib/ws", () => ({
  Realtime: class {
    constructor(options: RealtimeOptions) {
      made.options.push(options);
    }
    start = made.start;
    stop = made.stop;
  },
  setCurrentRealtime: (socket: unknown) => made.current.push(socket),
}));

beforeEach(() => {
  made.options.length = 0;
  made.current.length = 0;
  made.start.mockReset();
  made.stop.mockReset();
});

function mount(gender: "male" | "female" | null) {
  const client = makeQueryClient();
  if (gender) client.setQueryData(queryKeys.me(), { id: "me", gender });
  const view = render(
    <QueryClientProvider client={client}>
      <Realtime />
    </QueryClientProvider>,
  );
  return { client, view };
}

describe("the app's socket (T-7.12)", () => {
  it("opens once while mounted and closes when the app is left", async () => {
    const { view } = mount("male");
    await waitFor(() => expect(made.start).toHaveBeenCalledTimes(1));
    expect(made.current).toHaveLength(1);
    expect(made.current[0]).not.toBeNull();

    view.unmount();

    expect(made.stop).toHaveBeenCalledTimes(1);
    expect(made.current.at(-1)).toBeNull();
  });

  it("reads his events by his gender, and hers as hers (P-460)", async () => {
    const his = mount("male").client;
    await waitFor(() => expect(made.options).toHaveLength(1));
    const hisOptions = made.options[0] as RealtimeOptions;
    his.setQueryData(queryKeys.thread("t1"), { id: "t1" });

    act(() =>
      hisOptions.onEvent({
        type: "thread.expired",
        id: "e1",
        data: { thread_id: "t1" },
      }),
    );
    expect(his.getQueryState(queryKeys.thread("t1"))?.isInvalidated).toBe(true);

    const hers = mount("female").client;
    await waitFor(() => expect(made.options).toHaveLength(2));
    const herOptions = made.options[1] as RealtimeOptions;
    hers.setQueryData(queryKeys.thread("t1"), { id: "t1" });

    act(() =>
      herOptions.onEvent({
        type: "thread.expired",
        id: "e2",
        data: { thread_id: "t1" },
      }),
    );
    expect(hers.getQueryState(queryKeys.thread("t1"))?.isInvalidated).toBe(
      false,
    );
  });

  it("opens nothing when the app is left before its client has loaded (T-9.10)", async () => {
    const { view } = mount("male");
    view.unmount();

    // Long enough for the import to settle: the socket must still not open.
    await act(async () => {
      await import("@/lib/ws");
      await import("@/lib/queries/realtime");
      await new Promise((settled) => setTimeout(settled, 0));
    });
    expect(made.options).toHaveLength(0);
    expect(made.start).not.toHaveBeenCalled();
    expect(made.current).toEqual([]);
  });
});
