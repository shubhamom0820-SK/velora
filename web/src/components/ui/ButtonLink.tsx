import Link from "next/link";
import type { ComponentProps } from "react";

import { cx } from "@/lib/cx";

import {
  buttonClasses,
  type ButtonSize,
  type ButtonVariant,
} from "./buttonClasses";

type ButtonLinkProps = Omit<ComponentProps<typeof Link>, "className"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  /** Layout only (margins, flex), as on `Button`. */
  className?: string;
};

/**
 * A link drawn as a `Button`, for an action that goes somewhere ("Get started"
 * → `/login`). A server component: it ships no JavaScript of its own.
 */
export function ButtonLink({
  variant = "primary",
  size = "md",
  fullWidth = false,
  className,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link
      className={cx(
        buttonClasses({ variant, size, fullWidth }),
        "active:opacity-80",
        className,
      )}
      {...rest}
    />
  );
}
