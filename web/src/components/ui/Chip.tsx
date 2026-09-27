"use client";

import { X, type LucideIcon } from "lucide-react";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

import { Icon } from "./Icon";

type ChipProps = {
  children: string;
  icon?: LucideIcon;
  /** A toggle chip (filters, pickers): selected or not. Leave out for a plain action chip. */
  active?: boolean;
  onClick?: () => void;
  /** A removable chip shows an ✕ that calls this; it isn't itself a button. */
  onRemove?: () => void;
  disabled?: boolean;
};

const BASE =
  "rounded-pill text-ui inline-flex items-center gap-1.5 border px-3.5 py-2";
const ON = "border-accent bg-accent-soft text-accent font-semibold";
const OFF = "border-line text-mute font-normal";
// Drawn 38 px tall, as in the prototype; ::before stretches the tap area past 44 px.
const TAP = "relative before:absolute before:inset-x-0 before:-inset-y-1";
const FOCUS =
  "focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2";

export function Chip({
  children,
  icon,
  active,
  onClick,
  onRemove,
  disabled,
}: ChipProps) {
  const glyph = icon && <Icon icon={icon} size={14} />;

  if (onRemove) {
    return (
      <span className={cx(BASE, ON, "pr-2")}>
        {glyph}
        {children}
        <button
          type="button"
          aria-label={t("ui.remove", { label: children })}
          onClick={onRemove}
          disabled={disabled}
          className={cx(
            "rounded-pill relative before:absolute before:-inset-3",
            FOCUS,
          )}
        >
          <Icon icon={X} size={14} />
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      disabled={disabled}
      className={cx(
        BASE,
        active ? ON : OFF,
        TAP,
        FOCUS,
        "transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      {glyph}
      {children}
    </button>
  );
}
