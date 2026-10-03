import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { FirebasePhoneSignIn } from "@/lib/firebase";
import { useSession } from "@/store/session";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";
import type { Me } from "./me";

export type Seeking = components["schemas"]["Seeking"];
export type Gender = components["schemas"]["Gender"];

/** Path B's first half (T-3.2): text a code to `phone`, an E.164 number. */
export function useSendCode() {
  return useMutation({
    mutationFn: (phone: string) =>
      api.post("/v1/auth/otp/send", { body: { phone } }),
  });
}

/**
 * Path B's second half (T-3.3). The session starts here: `Me` goes into the
 * cache first, so the screens move on the moment the token arrives, and the
 * sign-in counts as fresh, so the PIN lock doesn't ask as well.
 */
export function useVerifyCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { phone: string; otp: string }) =>
      api.post("/v1/auth/otp/verify", { body }),
    onSuccess: ({ access_token, user }) => {
      queryClient.setQueryData(queryKeys.me(), user);
      useSession.getState().signIn(access_token, { fresh: true });
    },
  });
}

/**
 * How long Path A's code screen waits before offering a new code: Path B's
 * server says 45 s (T-3.2), and the screens are the same on both paths.
 * Firebase's own limits apply on top.
 */
export const FIREBASE_RESEND_AFTER_S = 45;

/**
 * Path A's first half (T-3.14): Firebase texts the code from the browser, so
 * our API isn't asked. Answers as Path B's send does, so one screen serves
 * both. `firebase` is null until the screen's Firebase has started.
 */
export function useFirebaseSendCode(firebase: FirebasePhoneSignIn | null) {
  return useMutation({
    mutationFn: async (phone: string) => {
      if (!firebase) throw new FirebaseNotReady();
      await firebase.sendCode(phone);
      return { resend_after_s: FIREBASE_RESEND_AFTER_S };
    },
  });
}

/**
 * Path A's second half (T-3.14, D-085): Firebase checks the code, our API
 * exchanges its ID token for our session, and Firebase's user is signed out
 * whatever the API said: we keep our own session. Then as Path B's verify.
 */
export function useFirebaseVerifyCode(firebase: FirebasePhoneSignIn | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ otp }: { phone: string; otp: string }) => {
      if (!firebase) throw new FirebaseNotReady();
      const idToken = await firebase.confirm(otp);
      try {
        return await api.post("/v1/auth/firebase", {
          body: { id_token: idToken },
        });
      } finally {
        // A failed sign-out is swallowed: it must not turn a sign-in that
        // worked into an error, and the user is in this tab's memory only.
        await firebase.signOut().catch(() => undefined);
      }
    },
    onSuccess: ({ access_token, user }) => {
      queryClient.setQueryData(queryKeys.me(), user);
      useSession.getState().signIn(access_token, { fresh: true });
    },
  });
}

/** The screen's Firebase hasn't started: its script didn't load, most likely. */
export class FirebaseNotReady extends Error {
  constructor() {
    super("Firebase hasn't started on this screen.");
    this.name = "FirebaseNotReady";
  }
}

/** An onboarding write that answers with the new `Me`, which replaces the cached one. */
function useMeMutation<T>(write: (input: T) => Promise<Me>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: write,
    onSuccess: (me) => queryClient.setQueryData(queryKeys.me(), me),
  });
}

export function useSetDob() {
  return useMeMutation((dob: string) =>
    api.post("/v1/me/dob", { body: { dob } }),
  );
}

export function useSetGender() {
  return useMeMutation((gender: Gender) =>
    api.post("/v1/me/gender", { body: { gender } }),
  );
}

export function useSetSeeking() {
  return useMeMutation((body: { seeking: Seeking; intent_ids: number[] }) =>
    api.post("/v1/me/seeking", { body }),
  );
}

export function useUpdateProfile() {
  return useMeMutation((body: components["schemas"]["ProfilePatch"]) =>
    api.patch("/v1/me/profile", { body }),
  );
}

export function useSetUsername() {
  return useMeMutation((username: string) =>
    api.put("/v1/me/username", { body: { username } }),
  );
}

/** The intents catalogue (D-041): ten rows that change by migration only. */
export function useIntents() {
  return useQuery({
    queryKey: queryKeys.intents(),
    queryFn: ({ signal }) => api.get("/v1/intents", { signal }),
    staleTime: Infinity,
  });
}

/** Whether `username` is free (T-3.7), once there's one worth asking about. */
export function useUsernameAvailability(username: string | null) {
  return useQuery({
    queryKey: queryKeys.usernameAvailable(username ?? ""),
    queryFn: ({ signal }) =>
      api.get("/v1/usernames/{username}/available", {
        params: { username: username ?? "" },
        signal,
      }),
    enabled: username !== null,
    staleTime: 30_000,
  });
}

export function useSetInterests() {
  return useMeMutation((interest_ids: number[]) =>
    api.put("/v1/me/interests", { body: { interest_ids } }),
  );
}

/** The interests catalogue (T-1.14): 24 rows that change by migration only. */
export function useInterests() {
  return useQuery({
    queryKey: queryKeys.interests(),
    queryFn: ({ signal }) => api.get("/v1/interests", { signal }),
    staleTime: Infinity,
  });
}

/**
 * Set the PIN at the `pin` step (D-069). The API answers 204, so `Me`, whose
 * step has moved on to `selfie`, is fetched afresh and handed back.
 */
export function useSetPin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (pin: string): Promise<Me> => {
      await api.post("/v1/auth/pin/set", { body: { pin } });
      return queryClient.fetchQuery({
        queryKey: queryKeys.me(),
        queryFn: ({ signal }) => api.get("/v1/me", { signal }),
        staleTime: 0,
      });
    },
  });
}

export function useSkipPin() {
  return useMeMutation(() => api.post("/v1/me/pin/skip"));
}
