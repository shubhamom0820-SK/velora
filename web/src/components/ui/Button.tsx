"use client";

import { Loader } from "lucide-react";
import type { ComponentPropsWithRef, MouseEvent } from "react";

import { cx } from "@/lib/cx";

import { Icon } from "./Icon";

type Variant = "primary" | "ghost" | "danger" | "chrome";
type Size = "sm" | "md";

type ButtonProps = Omit<ComponentPropsWithRef<"button">, "className"> & {
  /** `chrome` is the ghost button for black areas (header, hero, wallet card). */
  variant?: Variant;
  size?: Size;
  /** Shows a spinner and ignores clicks, so a double tap can't submit twice. */
  loading?: boolean;
  fullWidth?: boolean;
  /**
   * Layout only (margins, flex). Colour, size and width are props: `cx` joins
   * classes without resolving conflicts, so an override here wouldn't win.
   */
  className?: string;
};

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-on-accent font-bold shadow-1 disabled:bg-surface-2 disabled:text-mute disabled:shadow-none",
  ghost: "border border-line text-ink font-semibold disabled:text-mute",
  danger:
    "border border-accent text-accent font-semibold disabled:border-line disabled:text-mute",
  chrome:
    "border border-chrome-line text-chrome-ink font-semibold disabled:text-chrome-mute",
};

const SIZES: Record<Size, string> = {
  md: "px-6 py-3.5",
  // Drawn 40–42 px tall, as in the prototype; the invisible ::before stretches
  // the tap area past 44 px (08-DESIGN §3).
  sm: "px-4 py-2.5 before:absolute before:inset-x-0 before:-inset-y-1",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  className,
  type = "button",
  onClick,
  children,
  ...rest
}: ButtonProps) {
  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    if (loading) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  }

  return (
    <button
      type={type}
      // Not `disabled`: that would drop focus mid-submit and grey the button out.
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      onClick={handleClick}
      className={cx(
        "rounded-button text-ui focus-visible:outline-accent relative inline-flex items-center justify-center gap-2 transition-opacity duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 enabled:active:opacity-80 disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        fullWidth && "w-full",
        className,
      )}
      {...rest}
    >
      <span
        className={cx("inline-flex items-center gap-2", loading && "opacity-0")}
      >
        {children}
      </span>
      {loading && (
        <Icon
          icon={Loader}
          size={18}
          className="absolute motion-safe:animate-spin motion-reduce:animate-pulse"
        />
      )}
    </button>
  );
}
