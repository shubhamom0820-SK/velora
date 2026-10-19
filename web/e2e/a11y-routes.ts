/**
 * Every signed-in screen T-9.11's walk visits (`a11y.spec.ts`): each `(app)`
 * route for him and for her, each admin route for staff. A route is its
 * page file under `src/app`, so `src/lib/a11y-routes.test.ts` can hold this
 * list to the pages that exist: a new screen that isn't walked fails there,
 * before it reaches a person who can't use it (T-9.5's admin screens joined
 * this way).
 *
 * Plain data, no Playwright: the vitest guard imports it too.
 */

/** The ids a journey has made by the time it walks. */
export type WalkIds = {
  /** Their Thread. */
  thread: string;
  /** The other person, whose profile each opens. */
  other: string;
  /** Her account, which staff look up. */
  her: string;
};

export type WalkedRoute = {
  /** The page file, under src/app. */
  page: string;
  /** Who walks it: a man, a woman, or staff (D-963's role). */
  walkers: ReadonlyArray<"him" | "her" | "staff">;
  /** Where it is, with the journey's ids. */
  path: (ids: WalkIds) => string;
};

const PEOPLE = ["him", "her"] as const;
const STAFF = ["staff"] as const;

export const WALKED_ROUTES: readonly WalkedRoute[] = [
  { page: "(app)/discover/page.tsx", walkers: PEOPLE, path: () => "/discover" },
  {
    page: "(app)/discover/likes/page.tsx",
    walkers: PEOPLE,
    path: () => "/discover/likes",
  },
  {
    page: "(app)/discover/search/page.tsx",
    walkers: PEOPLE,
    path: () => "/discover/search",
  },
  { page: "(app)/chats/page.tsx", walkers: PEOPLE, path: () => "/chats" },
  {
    page: "(app)/chats/[id]/page.tsx",
    walkers: PEOPLE,
    path: ({ thread }) => `/chats/${thread}`,
  },
  {
    page: "(app)/people/[id]/page.tsx",
    walkers: PEOPLE,
    path: ({ other }) => `/people/${other}`,
  },
  {
    page: "(app)/notifications/page.tsx",
    walkers: PEOPLE,
    path: () => "/notifications",
  },
  { page: "(app)/wallet/page.tsx", walkers: PEOPLE, path: () => "/wallet" },
  { page: "(app)/you/page.tsx", walkers: PEOPLE, path: () => "/you" },
  { page: "(app)/you/edit/page.tsx", walkers: PEOPLE, path: () => "/you/edit" },
  {
    page: "(app)/you/photos/page.tsx",
    walkers: PEOPLE,
    path: () => "/you/photos",
  },
  {
    page: "(app)/you/settings/page.tsx",
    walkers: PEOPLE,
    path: () => "/you/settings",
  },
  {
    page: "(app)/you/notifications/page.tsx",
    walkers: PEOPLE,
    path: () => "/you/notifications",
  },
  {
    page: "(app)/you/album-requests/page.tsx",
    walkers: PEOPLE,
    path: () => "/you/album-requests",
  },
  { page: "admin/page.tsx", walkers: STAFF, path: () => "/admin" },
  {
    page: "admin/reports/page.tsx",
    walkers: STAFF,
    path: () => "/admin/reports",
  },
  {
    page: "admin/moderation/page.tsx",
    walkers: STAFF,
    path: () => "/admin/moderation",
  },
  {
    page: "admin/claims/page.tsx",
    walkers: STAFF,
    path: () => "/admin/claims",
  },
  {
    page: "admin/freezes/page.tsx",
    walkers: STAFF,
    path: () => "/admin/freezes",
  },
  {
    page: "admin/minor-flags/page.tsx",
    walkers: STAFF,
    path: () => "/admin/minor-flags",
  },
  { page: "admin/audit/page.tsx", walkers: STAFF, path: () => "/admin/audit" },
  { page: "admin/users/page.tsx", walkers: STAFF, path: () => "/admin/users" },
  {
    page: "admin/users/[id]/page.tsx",
    walkers: STAFF,
    path: ({ her }) => `/admin/users/${her}`,
  },
  {
    page: "admin/threads/[id]/page.tsx",
    walkers: STAFF,
    path: ({ thread }) => `/admin/threads/${thread}`,
  },
];

/** The route groups and folders whose every page must be walked. */
export const WALKED_ROOTS = ["(app)", "admin"] as const;
