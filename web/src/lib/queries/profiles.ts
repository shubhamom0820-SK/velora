import { useMutation, useQuery } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { components } from "@/types/api";

import { queryKeys } from "./keys";

export type PublicProfile = components["schemas"]["PublicProfile"];
export type SharedProfile = components["schemas"]["SharedProfile"];

/** One person's profile, as the viewer may see it (`GET /users/{id}`, D-493). */
export function useProfile(id: string) {
  return useQuery({
    queryKey: queryKeys.profile(id),
    queryFn: ({ signal }) =>
      api.get("/v1/users/{user_id}", { params: { user_id: id }, signal }),
  });
}

/**
 * The id behind a username (`GET /users/by-username/{u}`), for `/@username`'s
 * redirect of someone signed in to the in-app profile (T-6.8). Off until
 * `enabled`: only a signed-in, onboarded visitor may ask.
 */
export function useProfileByUsername(username: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.profileByUsername(username),
    queryFn: ({ signal }) =>
      api.get("/v1/users/by-username/{username}", {
        params: { username },
        signal,
      }),
    enabled,
    retry: false,
  });
}

/**
 * Like them from their profile (`POST /swipes`, T-6.4): free, and counted
 * toward a man's daily swipes as the deck's likes are.
 */
export function useLike() {
  return useMutation({
    mutationFn: (targetId: string) =>
      // A like is free: the price shown is 0 (P-56, D-600).
      api.post("/v1/swipes", {
        body: { target_id: targetId, dir: "like", shown_price: 0 },
      }),
  });
}

/**
 * What `/@username` shows someone not signed in (`GET /public-profiles/{u}`,
 * D-544), read by the page's server render; null when the API says
 * `NOT_FOUND`, which is every case but an opted-in, visible profile.
 */
export async function getSharedProfile(
  username: string,
): Promise<SharedProfile | null> {
  try {
    return await api.get("/v1/public-profiles/{username}", {
      params: { username },
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}
