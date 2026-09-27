/**
 * The one colour literal outside tokens.css (08-DESIGN §1). `<meta
 * name="theme-color">` can't read a CSS variable, so the root layout needs the
 * value itself. It must equal `--chrome` in tokens.css, and theme-color.test.ts
 * fails if it doesn't (P-28).
 */
export const THEME_COLOR = "#141113";
