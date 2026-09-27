"use client";

import { useId } from "react";

import { cx } from "@/lib/cx";

type ToggleProps = {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
};

/** An on/off setting. The whole row is the switch, as in the prototype's settings sheets. */
export function Toggle({
  label,
  description,
  checked,
  onChange,
  disabled,
}: ToggleProps) {
  const id = useId();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-labelledby={`${id}-label`}
      aria-describedby={description ? `${id}-description` : undefined}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="rounded-input focus-visible:outline-accent flex w-full items-center justify-between gap-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className="flex flex-col">
        <span id={`${id}-label`} className="text-ui text-ink">
          {label}
        </span>
        {description && (
          <span id={`${id}-description`} className="text-small text-mute">
            {description}
          </span>
        )}
      </span>
      <span
        aria-hidden
        className={cx(
          "rounded-pill flex h-6 w-[42px] shrink-0 items-center p-0.5 transition-colors duration-150",
          checked ? "bg-accent justify-end" : "bg-line-strong justify-start",
        )}
      >
        <span className="rounded-pill bg-surface shadow-knob size-5" />
      </span>
    </button>
  );
}
