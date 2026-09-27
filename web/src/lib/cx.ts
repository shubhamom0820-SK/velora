/** Joins class names, skipping falsy ones: `cx("a", on && "b")`. */
export function cx(
  ...classes: ReadonlyArray<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}
