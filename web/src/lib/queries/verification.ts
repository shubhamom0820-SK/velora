import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import { putToStorage } from "@/lib/upload";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";
import type { Photo } from "./photos";

/**
 * A verification as its owner sees it (T-4.5, D-263): never a number, a link
 * or the selfie. `approved` means the selfie's face matched one of the
 * profile's photos, and nothing more is claimed (D-262).
 */
export type Verification = components["schemas"]["Verification"];

/**
 * How often the selfie step asks while a selfie is being compared, and for how
 * long (T-4.7). The worker is woken the moment a selfie is sent (D-261), so a
 * result usually comes within seconds; a lost wake leaves it to the queue,
 * within D-091's 10 seconds. After a minute the screen stops asking and offers
 * to check again. Asked only while the tab is visible (TanStack's default), so
 * a person who leaves costs nothing, and the result is read when they're back.
 */
export const VERIFICATION_POLL_MS = 2_000;
export const VERIFICATION_POLL_FOR_MS = 60_000;

/** Pending with a selfie attached: being compared now. */
export function isBeingCompared(verification: Verification | null): boolean {
  return (
    verification !== null &&
    verification.status === "pending" &&
    verification.submitted
  );
}

/**
 * The newest verification (`GET /verification/latest`), or null when there's
 * none yet (`NOT_FOUND`). With `poll`, asked again every
 * `VERIFICATION_POLL_MS` while it's being compared.
 */
export function useLatestVerification({ poll }: { poll: boolean }) {
  return useQuery({
    queryKey: queryKeys.verificationLatest(),
    queryFn: async ({ signal }): Promise<Verification | null> => {
      try {
        return await api.get("/v1/verification/latest", { signal });
      } catch (error) {
        if (error instanceof ApiError && error.code === "NOT_FOUND")
          return null;
        throw error;
      }
    },
    refetchInterval: (query) =>
      poll && isBeingCompared(query.state.data ?? null)
        ? VERIFICATION_POLL_MS
        : false,
  });
}

/**
 * Start a verification (`POST /verification/start`): the one already open, or
 * a new one, waiting for its selfie. No pose is asked (T-4.5, D-263).
 */
export function useStartVerification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/v1/verification/start"),
    onSuccess: (verification) =>
      queryClient.setQueryData(queryKeys.verificationLatest(), verification),
  });
}

export type SelfieUpload = {
  /** The captured frame, a JPEG (src/lib/camera.ts). */
  body: Blob;
  onProgress?: (percent: number) => void;
};

/**
 * One selfie up (T-4.2's flow, `kind: "selfie"`): a presigned URL, the PUT
 * straight to the private bucket with exactly the signed headers, then
 * `complete`, which reads the bytes (D-089). The answer is the selfie, pending,
 * not yet sent to a verification. One that never arrives, or is never sent, is
 * replaced by the next upload, its file deleted (D-263), so nothing is cleaned
 * up here: a selfie can't be deleted by its owner anyway (T-4.3).
 */
export function useUploadSelfie() {
  return useMutation({
    mutationFn: async ({ body, onProgress }: SelfieUpload): Promise<Photo> => {
      const { photo_id, put_url, headers } = await api.post(
        "/v1/photos/upload-url",
        { body: { kind: "selfie", content_type: body.type } },
      );
      await putToStorage(put_url, body, headers, { onProgress });
      return api.post("/v1/photos/{photo_id}/complete", {
        params: { photo_id },
      });
    },
  });
}

/**
 * Send the uploaded selfie to the verification
 * (`POST /verification/{id}/submit`): one of the day's five. The API queues the
 * comparison and wakes the worker (D-261); the answer is pending and
 * `submitted`, which `useLatestVerification` then follows.
 */
export function useSubmitSelfie() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      verificationId,
      photoId,
    }: {
      verificationId: string;
      photoId: string;
    }) =>
      api.post("/v1/verification/{verification_id}/submit", {
        params: { verification_id: verificationId },
        body: { photo_id: photoId },
      }),
    onSuccess: (verification) =>
      queryClient.setQueryData(queryKeys.verificationLatest(), verification),
  });
}
