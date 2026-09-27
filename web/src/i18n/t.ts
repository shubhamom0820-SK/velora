import { en } from "./en";

type Dictionary = { readonly [key: string]: string | Dictionary };

/** Every dotted path in `en` that ends at a string, e.g. `"placeholder.login"`. */
type Leaves<T, Prefix extends string = ""> = {
  [K in keyof T & string]: T[K] extends string
    ? `${Prefix}${K}`
    : Leaves<T[K], `${Prefix}${K}.`>;
}[keyof T & string];

export type MessageKey = Leaves<typeof en>;

/**
 * The string for `key`, with `{name}` placeholders filled from `values`. A key
 * that isn't in `en` doesn't compile; a placeholder with no value stays visible
 * rather than rendering as "undefined".
 */
export function t(
  key: MessageKey,
  values?: Readonly<Record<string, string | number>>,
): string {
  let node: string | Dictionary = en;
  for (const part of key.split(".")) {
    if (typeof node === "string") break;
    const next: string | Dictionary | undefined = node[part];
    if (next === undefined) break;
    node = next;
  }
  if (typeof node !== "string") {
    throw new Error(`No string for "${key}"`);
  }
  if (!values) return node;
  return node.replace(/\{(\w+)\}/g, (placeholder, name: string) => {
    const value = values[name];
    return value === undefined ? placeholder : String(value);
  });
}
