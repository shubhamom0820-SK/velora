/**
 * What the search field asks for, by the API's own rules (D-540,
 * `discovery/rules.py`), so the screen asks only what the API would answer
 * and says why when it can't: `@` and 1 to 20 of a-z, 0-9, `.` and `_`, any
 * case; or text of 2 to 50 characters. Spaces around it don't count.
 */

/** `q`, whole, `@` included: the API's `SEARCH_MAX`. */
export const SEARCH_MAX = 50;
/** Text needs this many characters: the API's `SEARCH_TEXT_MIN`. */
export const SEARCH_TEXT_MIN = 2;

const USERNAME_PREFIX = /^[A-Za-z0-9._]{1,20}$/;

export type SearchQuery =
  | { kind: "empty" }
  | { kind: "username"; q: string }
  | { kind: "text"; q: string }
  | { kind: "tooShort" }
  | { kind: "badUsername" };

export function searchQueryOf(raw: string): SearchQuery {
  const q = raw.trim();
  if (q === "" || q === "@") return { kind: "empty" };
  if (q.startsWith("@")) {
    const term = q.slice(1);
    return USERNAME_PREFIX.test(term)
      ? { kind: "username", q: `@${term.toLowerCase()}` }
      : { kind: "badUsername" };
  }
  if (q.length < SEARCH_TEXT_MIN) return { kind: "tooShort" };
  return { kind: "text", q };
}
