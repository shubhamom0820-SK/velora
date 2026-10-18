"use client";

import { useRef, type ClipboardEvent, type KeyboardEvent } from "react";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

type OtpInputProps = {
  value: string;
  onChange: (value: string) => void;
  /** Called once all the digits are in. */
  onComplete?: (value: string) => void;
  length?: number;
  /** Names the group for screen readers. */
  label: string;
  invalid?: boolean;
  disabled?: boolean;
  autoFocus?: boolean;
};

const BOX =
  "rounded-input text-title-1 border-line bg-surface text-ink h-14 w-full min-w-0 border text-center font-semibold focus-visible:border-accent disabled:opacity-50";

/**
 * The code boxes (08-DESIGN §4): 6 of them (D-066; the prototype's 4 are
 * historical). Pasting, or a phone filling in the texted code, spreads the
 * digits across the boxes; typing moves on; Backspace in an empty box goes
 * back. Only digits are kept.
 */
export function OtpInput({
  value,
  onChange,
  onComplete,
  length = 6,
  label,
  invalid = false,
  disabled = false,
  autoFocus = false,
}: OtpInputProps) {
  const boxes = useRef<(HTMLInputElement | null)[]>([]);

  function put(from: number, typed: string) {
    const digits = typed.replace(/\D/g, "");
    if (!digits) return;
    const next = (value.slice(0, from) + digits).slice(0, length);
    onChange(next);
    boxes.current[Math.min(next.length, length - 1)]?.focus();
    if (next.length === length) onComplete?.(next);
  }

  function onKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Backspace") return;
    event.preventDefault();
    if (value[index] !== undefined) {
      onChange(value.slice(0, index));
    } else if (index > 0) {
      onChange(value.slice(0, index - 1));
      boxes.current[index - 1]?.focus();
    }
  }

  function onPaste(index: number, event: ClipboardEvent<HTMLInputElement>) {
    event.preventDefault();
    put(index, event.clipboardData.getData("text"));
  }

  return (
    <div role="group" aria-label={label} className="flex gap-2.5">
      {Array.from({ length }, (_, index) => (
        <input
          key={index}
          ref={(element) => {
            boxes.current[index] = element;
          }}
          aria-label={t("ui.otpDigit", { n: index + 1, total: length })}
          aria-invalid={invalid || undefined}
          // The first box takes the phone's SMS autofill; it spreads the rest.
          autoComplete={index === 0 ? "one-time-code" : "off"}
          inputMode="numeric"
          pattern="[0-9]*"
          autoFocus={autoFocus && index === 0}
          disabled={disabled}
          value={value[index] ?? ""}
          onChange={(event) =>
            put(
              Math.min(index, value.length),
              // A box that had a digit keeps only the one just typed.
              value[index] === undefined
                ? event.target.value
                : event.target.value.slice(-1),
            )
          }
          onKeyDown={(event) => onKeyDown(index, event)}
          onPaste={(event) => onPaste(index, event)}
          className={cx(BOX, invalid && "border-accent")}
        />
      ))}
    </div>
  );
}
