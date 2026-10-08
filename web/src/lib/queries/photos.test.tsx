import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { envelope, fakeApi, json } from "@/lib/testing/fakeApi";
import { fakeXhr } from "@/lib/testing/fakeXhr";
import { resetSession } from "@/store/session";

import { queryKeys } from "./keys";
import {
  facePhoto,
  PHOTO_POLL_MS,
  publicPhotos,
  shownCopy,
  useDeletePhoto,
  useFinishPhotos,
  useMyPhotos,
  usePhotoOutcomes,
  useShowFacePhoto,
  useUploadFacePhoto,
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
    from_photo_id: null,
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
  it("closes a gap first, then leaves the step by its own exit, which answers Me (T-4.12)", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, [photo({ position: 3 })]),
      "PATCH /v1/me/photos/order": () => json(200, [photo()]),
      "POST /v1/me/photos/done": () =>
        json(200, { onboarding_step: "interests" }),
    });
    const { result } = renderHook(() => useFinishPhotos(), { wrapper });

    const me = await result.current.mutateAsync();

    expect(me.onboarding_step).toBe("interests");
    expect(api_.sent()).toEqual([
      "GET /v1/me/photos",
      "PATCH /v1/me/photos/order",
      "POST /v1/me/photos/done",
    ]);
    expect(api_.calls[1]?.body).toEqual({ photo_ids: ["p1"] });
    expect(client.getQueryData(["me"])).toEqual({
      onboarding_step: "interests",
    });
  });

  it("leaves with no photo at all, and hands on the server's refusal", async () => {
    const api_ = fakeApi({
      "GET /v1/me/photos": () => json(200, []),
      "POST /v1/me/photos/done": () => envelope(403, "FACE_PHOTO_REQUIRED"),
    });
    const { result } = renderHook(() => useFinishPhotos(), { wrapper });

    await expect(result.current.mutateAsync()).rejects.toMatchObject({
      code: "FACE_PHOTO_REQUIRED",
    });
    expect(api_.sent()).toEqual([
      "GET /v1/me/photos",
      "POST /v1/me/photos/done",
    ]);
  });
});

describe("the face photo (T-4.12)", () => {
  it("is the one of kind verification, and its shown copy the public one made from it", () => {
    const face = photo({ id: "f1", kind: "verification", position: null });
    const copy = photo({ id: "c1", position: 1, from_photo_id: "f1" });
    const photos = [photo(), copy, face];

    expect(facePhoto(photos)).toBe(face);
    expect(facePhoto([photo()])).toBeNull();
    expect(shownCopy(photos, "f1")).toBe(copy);
    expect(shownCopy([photo(), face], "f1")).toBeNull();
    expect(publicPhotos(photos).map((p) => p.id)).toEqual(["p1", "c1"]);
  });

  it("uploads it as kind verification with no place, PUTs, then completes, and asks for the list again", async () => {
    const xhr = fakeXhr();
    const api_ = fakeApi({
      "POST /v1/photos/upload-url": () =>
        json(200, {
          photo_id: "f1",
          put_url: PUT_URL,
          headers: { "Content-Type": "image/jpeg" },
        }),
      "POST /v1/photos/f1/complete": () =>
        json(
          200,
          photo({
            id: "f1",
            kind: "verification",
            position: null,
            status: "pending",
          }),
        ),
      "GET /v1/me/photos": () => json(200, []),
    });
    const invalidated = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useUploadFacePhoto(), { wrapper });
    const body = new Blob(["jpeg"], { type: "image/jpeg" });

    const sent = result.current.mutateAsync({ body });
    await waitFor(() => expect(xhr.requests).toHaveLength(1));
    xhr.requests[0]?.respond(200);
    const uploaded = await sent;

    expect(uploaded.kind).toBe("verification");
    expect(api_.calls[0]?.body).toEqual({
      kind: "verification",
      content_type: "image/jpeg",
    });
    expect(api_.sent()).toEqual([
      "POST /v1/photos/upload-url",
      "POST /v1/photos/f1/complete",
    ]);
    expect(invalidated).toHaveBeenCalledWith({
      queryKey: queryKeys.myPhotos(),
    });
  });

  it("shows it on the profile by asking for the copy, then asks for the list again", async () => {
    const api_ = fakeApi({
      "POST /v1/photos/f1/show": () =>
        json(
          200,
          photo({
            id: "c1",
            position: 0,
            status: "pending",
            from_photo_id: "f1",
          }),
        ),
      "GET /v1/me/photos": () => json(200, []),
    });
    const invalidated = vi.spyOn(client, "invalidateQueries");
    const { result } = renderHook(() => useShowFacePhoto(), { wrapper });

    const copy = await result.current.mutateAsync("f1");

    expect(copy.from_photo_id).toBe("f1");
    expect(api_.sent()).toEqual(["POST /v1/photos/f1/show"]);
    expect(invalidated).toHaveBeenCalledWith({
      queryKey: queryKeys.myPhotos(),
    });
  });
});
