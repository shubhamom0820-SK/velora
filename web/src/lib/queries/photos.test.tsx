import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";
import { fakeXhr } from "@/lib/testing/fakeXhr";
import { resetSession } from "@/store/session";

import { queryKeys } from "./keys";
import {
  PHOTO_POLL_MS,
  publicPhotos,
  useDeletePhoto,
  useFinishPhotos,
  useMyPhotos,
  usePhotoOutcomes,
  useUploadPhoto,
  type Photo,
} from "./photos";

const PUT_URL = "https://storage.test/velora-private/raw/u1/p1?sig=s";

function photo(overrides: Partial<Photo> = {}): Photo {
  return {
    id: "p1",
    kind: "public",
    position: 0,
    status: "approved",
    reject_reason: null,
    url: "https://cdn.test/p/p1.jpg",
    ...overrides,
  };
}

let client: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.test");
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  resetSession();
});

describe("publicPhotos", () => {
  it("keeps the public ones, by place", () => {
    const listed = [
      photo({ id: "b", position: 2 }),
      photo({ id: "x", kind: "private", position: null }),
      photo({ id: "a", position: 0 }),
    ];

    expect(publicPhotos(listed).map((p) => p.id)).toEqual(["a", "b"]);
  });
});

describe("useMyPhotos", () => {
  it.each([
    ["while a photo is being checked", "pending", 2],
    ["not once every photo is decided", "approved", 1],
  ] as const)("asks again %s", async (_, status, asks) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, [photo({ status })]),
    });
    const { result } = renderHook(() => useMyPhotos(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    await vi.advanceTimersByTimeAsync(PHOTO_POLL_MS + 100);

    await waitFor(() => expect(api_.sent()).toHaveLength(asks));
  });
});

describe("usePhotoOutcomes (D-096)", () => {
  it("asks how each vanished photo ended, once", async () => {
    const api_ = fakeApi({
      "GET /v1/photos/p1": () =>
        json(200, photo({ status: "rejected", reject_reason: "no_face" })),
    });

    const { result, rerender } = renderHook(() => usePhotoOutcomes(["p1"]), {
      wrapper,
    });
    await waitFor(() =>
      expect(result.current[0]?.data?.status).toBe("rejected"),
    );
    rerender();

    expect(api_.sent()).toEqual(["GET /v1/photos/p1"]);
  });
});

describe("useUploadPhoto", () => {
  it("asks for a place, PUTs, then completes, and asks for the list and Me again", async () => {
    const api_ = fakeApi({
      "POST /v1/photos/upload-url": () =>
        json(200, {
          photo_id: "p1",
          put_url: PUT_URL,
          headers: { "Content-Type": "image/png" },
        }),
      "POST /v1/photos/p1/complete": () =>
        json(200, photo({ status: "pending" })),
    });
    fakeXhr((request) => queueMicrotask(() => request.respond(200)));
    const invalidated = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useUploadPhoto(), { wrapper });

    const done = await result.current.mutateAsync({
      body: new Blob(["png"], { type: "image/png" }),
      position: 2,
    });

    expect(done.status).toBe("pending");
    expect(api_.sent()).toEqual([
      "POST /v1/photos/upload-url",
      "POST /v1/photos/p1/complete",
    ]);
    // The declared type is the body's own: a hint the server checks (D-089).
    expect(api_.calls[0]?.body).toEqual({
      kind: "public",
      position: 2,
      content_type: "image/png",
    });
    expect(invalidated).toHaveBeenCalledWith({
      queryKey: queryKeys.myPhotos(),
    });
    expect(invalidated).toHaveBeenCalledWith({ queryKey: queryKeys.me() });
  });

  it("gives the place back when the PUT fails, and never says it's complete", async () => {
    const api_ = fakeApi({
      "POST /v1/photos/upload-url": () =>
        json(200, { photo_id: "p1", put_url: PUT_URL, headers: {} }),
      "DELETE /v1/photos/p1": () => json(204),
    });
    fakeXhr((request) => queueMicrotask(() => request.respond(403)));
    const { result } = renderHook(() => useUploadPhoto(), { wrapper });

    await expect(
      result.current.mutateAsync({ body: new Blob(["x"]), position: 0 }),
    ).rejects.toMatchObject({ failure: "refused", status: 403 });

    expect(api_.sent()).toEqual([
      "POST /v1/photos/upload-url",
      "DELETE /v1/photos/p1",
    ]);
  });

  it("uploads nothing when the API refuses the place", async () => {
    const api_ = fakeApi({
      "POST /v1/photos/upload-url": () => envelope(422, "UNSUPPORTED_IMAGE"),
    });
    const xhr = fakeXhr();
    const { result } = renderHook(() => useUploadPhoto(), { wrapper });

    await expect(
      result.current.mutateAsync({ body: new Blob(["?"]), position: 0 }),
    ).rejects.toMatchObject({ code: "UNSUPPORTED_IMAGE" });

    expect(xhr.requests).toHaveLength(0);
    expect(api_.sent()).toEqual(["POST /v1/photos/upload-url"]);
  });
});

describe("useDeletePhoto", () => {
  it("leaves the order alone when no gap is left", async () => {
    const api_ = fakeApi({
      "DELETE /v1/photos/p2": () => json(204),
      "GET /v1/me/photos": () => json(200, [photo()]),
    });
    const { result } = renderHook(() => useDeletePhoto(), { wrapper });

    await result.current.mutateAsync("p2");

    expect(api_.sent()).toEqual(["DELETE /v1/photos/p2", "GET /v1/me/photos"]);
    expect(client.getQueryData(queryKeys.myPhotos())).toEqual([photo()]);
  });
});

describe("useFinishPhotos", () => {
  it("closes a gap first, then hands back Me as the API now has it", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, [photo({ position: 3 })]),
      "PATCH /v1/me/photos/order": () => json(200, [photo()]),
      "GET /v1/me": () => json(200, { onboarding_step: "interests" }),
    });
    const { result } = renderHook(() => useFinishPhotos(), { wrapper });

    const me = await result.current.mutateAsync();

    expect(me.onboarding_step).toBe("interests");
    expect(api_.sent()).toEqual([
      "GET /v1/me/photos",
      "PATCH /v1/me/photos/order",
      "GET /v1/me",
    ]);
    expect(api_.calls[1]?.body).toEqual({ photo_ids: ["p1"] });
  });
});
