"use client";

import { Loader } from "lucide-react";
import type { ComponentPropsWithRef, MouseEvent } from "react";

import { cx } from "@/lib/cx";

import {
  buttonClasses,
  type ButtonSize,
  type ButtonVariant,
} from "./buttonClasses";
import { Icon } from "./Icon";

type ButtonProps = Omit<ComponentPropsWithRef<"button">, "className"> & {
  /** `chrome` is the ghost button for black areas (header, hero, wallet card). */
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and ignores clicks, so a double tap can't submit twice. */
  loading?: boolean;
  fullWidth?: boolean;
  /**
   * Layout only (margins, flex). Colour, size and width are props: `cx` joins
   * classes without resolving conflicts, so an override here wouldn't win.
   */
  className?: string;
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
        buttonClasses({ variant, size, fullWidth }),
        "enabled:active:opacity-80 disabled:cursor-not-allowed",
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
