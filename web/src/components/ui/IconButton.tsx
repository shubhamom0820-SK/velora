import type { LucideIcon } from "lucide-react";
import type { ComponentPropsWithRef, ReactNode } from "react";

import { cx } from "@/lib/cx";

import { Icon } from "./Icon";

type IconButtonProps = Omit<
  ComponentPropsWithRef<"button">,
  "className" | "children" | "aria-label"
> & {
  icon: LucideIcon;
  /** The button's name for screen readers; an icon alone says nothing. */
  label: string;
  /** Diameter in px (08-DESIGN §4). Under 44, the tap area reaches past it. */
  size?: 40 | 46 | 56;
  /**
   * `ink`: an outlined `--ink` glyph (Pass, Search); `accent`: an outlined
   * `--accent` glyph (Super); `filled`: `--accent` with `--shadow-1` (Like).
   */
  tone?: "ink" | "accent" | "filled";
  /** A badge at the top right, e.g. a `PriceTag` or a count. */
  badge?: ReactNode;
  /** Layout only (margins, flex). */
  className?: string;
};

const SIZES = {
  40: { box: "size-10", glyph: 18, tap: "before:absolute before:-inset-0.5" },
  46: { box: "size-11.5", glyph: 22, tap: "" },
  56: { box: "size-14", glyph: 26, tap: "" },
} as const;

const TONES = {
  ink: "border border-line bg-surface text-ink",
  accent: "border border-line bg-surface text-accent",
  filled: "bg-accent text-on-accent shadow-1",
} as const;

/** A round button with one icon (08-DESIGN §4), optionally badged. */
export function IconButton({
  icon,
  label,
  size = 46,
  tone = "ink",
  badge,
  className,
  type = "button",
  ...rest
}: IconButtonProps) {
  const shape = SIZES[size];
  return (
    <button
      type={type}
      aria-label={label}
      className={cx(
        "rounded-pill focus-visible:outline-accent relative inline-flex shrink-0 items-center justify-center transition-opacity duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-40",
        shape.box,
        shape.tap,
        TONES[tone],
        className,
      )}
      {...rest}
    >
      <Icon icon={icon} size={shape.glyph} />
      {badge && <span className="absolute -top-1.5 -right-1.5">{badge}</span>}
    </button>
  );
}
