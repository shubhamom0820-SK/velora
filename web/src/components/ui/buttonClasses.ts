import { cx } from "@/lib/cx";

export type ButtonVariant = "primary" | "ghost" | "danger" | "chrome";
export type ButtonSize = "sm" | "md";

const BASE =
  "rounded-button text-ui focus-visible:outline-accent relative inline-flex items-center justify-center gap-2 transition-opacity duration-150 focus-visible:outline-2 focus-visible:outline-offset-2";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-accent text-on-accent font-bold shadow-1 disabled:bg-surface-2 disabled:text-mute disabled:shadow-none",
  ghost: "border border-line text-ink font-semibold disabled:text-mute",
  danger:
    "border border-accent text-accent font-semibold disabled:border-line disabled:text-mute",
  chrome:
    "border border-chrome-line text-chrome-ink font-semibold disabled:text-chrome-mute",
};

const SIZES: Record<ButtonSize, string> = {
  md: "px-6 py-3.5",
  // Drawn 40–42 px tall, as in the prototype; the invisible ::before stretches
  // the tap area past 44 px (08-DESIGN §3).
  sm: "px-4 py-2.5 before:absolute before:inset-x-0 before:-inset-y-1",
};

/**
 * How a button looks, shared by `Button` and `ButtonLink` so a link drawn as a
 * button is the same button. Press and disabled behaviour stay with each one:
 * a link has no `:enabled` state.
 */
export function buttonClasses({
  variant = "primary",
  size = "md",
  fullWidth = false,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
}): string {
  return cx(BASE, VARIANTS[variant], SIZES[size], fullWidth && "w-full");
}
