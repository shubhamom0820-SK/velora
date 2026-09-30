/**
 * Every query key, built here so a component can't typo one and an
 * invalidation can't miss one. Each key starts with its feature, so
 * `invalidateQueries({ queryKey: ["threads"] })` reaches every thread query.
 * Features add their keys when they add their hooks.
 */
export const queryKeys = {
  health: () => ["health"] as const,
};
