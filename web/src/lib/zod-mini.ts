import {
  boolean,
  config,
  int,
  object,
  record,
  string,
  unknown,
  type infer as ZodInfer,
} from "zod/mini";

/**
 * zod's small build, for code every `(app)` page loads (T-9.10, D-1032): the
 * socket's envelope and its events. `@/lib/zod` exports zod's whole `z`, which
 * no bundler can trim, so every page carried zod with every one of its
 * locales, about 63 KB gzipped of a 250 KB budget. Named imports of
 * `zod/mini` keep only what is used.
 *
 * jitless as `@/lib/zod` is, for the same reason (T-3.11): the setting is
 * zod's core's, shared by both builds, so either module turns the eval probe
 * off. Add a function here when a schema needs one; ESLint refuses zod
 * anywhere but this file and `@/lib/zod`.
 */
config({ jitless: true });

export const z = { boolean, config, int, object, record, string, unknown };

/** A schema's type, as `z.infer` in `@/lib/zod`. */
export type Infer<T> = ZodInfer<T>;
