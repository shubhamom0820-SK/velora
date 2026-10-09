import { QueryClientProvider } from "@tanstack/react-query";
import { act, render } from "@testing-library/react";
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
  it("opens once while mounted and closes when the app is left", () => {
    const { view } = mount("male");
    expect(made.start).toHaveBeenCalledTimes(1);
    expect(made.current).toHaveLength(1);
    expect(made.current[0]).not.toBeNull();

    view.unmount();

    expect(made.stop).toHaveBeenCalledTimes(1);
    expect(made.current.at(-1)).toBeNull();
  });

  it("reads his events by his gender, and hers as hers (P-460)", () => {
    const his = mount("male").client;
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
});
