import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { api } from "@/lib/api";
import { putToStorage } from "@/lib/upload";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";
import type { Me } from "./me";

export type Photo = components["schemas"]["Photo"];

/**
 * How often the photos step asks again while a photo is being checked. The
 * worker picks a job up within 10 s (D-091), so a result shows within about
 * 15 s of its upload. Asked only while the tab is visible (TanStack's default).
 */
export const PHOTO_POLL_MS = 5_000;

const isPending = (photo: Photo) => photo.status === "pending";

/** The live public photos, by place. */
export function publicPhotos(photos: readonly Photo[]): Photo[] {
  return photos
    .filter((photo) => photo.kind === "public")
    .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));
}

/**
 * The person's live photos (`GET /me/photos`, T-4.3): pending and approved,
 * never rejected ones, which leave the list (`usePhotoOutcomes` says why).
 * Asked again every `PHOTO_POLL_MS` while any is still being checked.
 */
export function useMyPhotos() {
  return useQuery({
    queryKey: queryKeys.myPhotos(),
    queryFn: ({ signal }) => api.get("/v1/me/photos", { signal }),
    refetchInterval: (query) =>
      query.state.data?.some(isPending) ? PHOTO_POLL_MS : false,
  });
}

/**
 * How each of these photos ended (`GET /photos/{id}`, D-096): asked once a
 * photo the step showed has left `GET /me/photos`, so its slot can say why.
 * An ending never changes, so each is asked once.
 */
export function usePhotoOutcomes(ids: readonly string[]) {
  return useQueries({
    queries: ids.map((id) => ({
      queryKey: queryKeys.photo(id),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api.get("/v1/photos/{photo_id}", { params: { photo_id: id }, signal }),
      staleTime: Infinity,
    })),
  });
}

export type UploadInput = {
  /** What goes up: the resized JPEG, or the file as picked if it couldn't be. */
  body: Blob;
  /** The public place, 0 to 5; 0 is the main photo. */
  position: number;
  onProgress?: (percent: number) => void;
};

/**
 * One public photo, start to end (T-4.2): a place and a presigned URL, the
 * PUT straight to storage with exactly the signed headers, then `complete`,
 * whose answer is the photo, pending. The declared type is the body's own,
 * a hint the server checks against the bytes (D-089).
 *
 * An upload that never arrives gives its place back at once, rather than
 * holding it until the API treats it as abandoned (T-4.2). `complete` moves
 * the person past the photos step on their first public photo (T-4.3), so
 * `Me` is asked again.
 */
export function useUploadPhoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      body,
      position,
      onProgress,
    }: UploadInput): Promise<Photo> => {
      const { photo_id, put_url, headers } = await api.post(
        "/v1/photos/upload-url",
        { body: { kind: "public", position, content_type: body.type } },
      );
      try {
        await putToStorage(put_url, body, headers, { onProgress });
      } catch (error) {
        await api
          .delete("/v1/photos/{photo_id}", { params: { photo_id } })
          .catch(() => undefined);
        throw error;
      }
      return api.post("/v1/photos/{photo_id}/complete", {
        params: { photo_id },
      });
    },
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.myPhotos() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.me() }),
      ]),
  });
}

/**
 * Put the public photos in this order, the first the main one: places 0
 * onwards (`PATCH /me/photos/order`). The answer is the new list.
 */
export function useReorderPhotos() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids: string[]) =>
      api.patch("/v1/me/photos/order", { body: { photo_ids: ids } }),
    onSuccess: (photos) =>
      queryClient.setQueryData(queryKeys.myPhotos(), photos),
    onError: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.myPhotos() }),
  });
}

/**
 * Close any gap in the public places, so they run 0 onwards and 0 is the main
 * photo (03-SCHEMA), as the prototype's grid keeps them. Read from a fresh
 * list, since the order must name every live public photo (T-4.3); the answer
 * is the list as it now is.
 */
async function closeGaps(): Promise<Photo[]> {
  const photos = await api.get("/v1/me/photos");
  const ordered = publicPhotos(photos);
  if (ordered.every((photo, place) => photo.position === place)) return photos;
  return api.patch("/v1/me/photos/order", {
    body: { photo_ids: ordered.map((photo) => photo.id) },
  });
}

/** Remove a photo (`DELETE /photos/{id}`), then close the gap it left. */
export function useDeletePhoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (photoId: string): Promise<Photo[]> => {
      await api.delete("/v1/photos/{photo_id}", {
        params: { photo_id: photoId },
      });
      return closeGaps();
    },
    onSuccess: (photos) =>
      queryClient.setQueryData(queryKeys.myPhotos(), photos),
    onError: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.myPhotos() }),
  });
}

/** Close a gap a rejected photo left, once its slot is cleared. */
export function useClosePhotoGaps() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: closeGaps,
    onSuccess: (photos) =>
      queryClient.setQueryData(queryKeys.myPhotos(), photos),
  });
}

/**
 * Leave the photos step: close any gap, so the main photo is in place 0, then
 * read `Me` afresh, whose step the API moved on at the first public photo
 * (T-4.3). The screen goes where `Me` now says.
 */
export function useFinishPhotos() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<Me> => {
      queryClient.setQueryData(queryKeys.myPhotos(), await closeGaps());
      return queryClient.fetchQuery({
        queryKey: queryKeys.me(),
        queryFn: ({ signal }) => api.get("/v1/me", { signal }),
        staleTime: 0,
      });
    },
  });
}
