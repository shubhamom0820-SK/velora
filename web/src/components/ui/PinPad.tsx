"use client";

import { Delete } from "lucide-react";
import { useEffect, useRef } from "react";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

import { Icon } from "./Icon";

type PinPadProps = {
  value: string;
  onChange: (value: string) => void;
  /** Called once, when the last digit goes in. */
  onComplete: (value: string) => void;
  length?: number;
  disabled?: boolean;
  /** `chrome` on the black lock screen (08-DESIGN §1). */
  tone?: "light" | "chrome";
};

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "delete"];

const FOCUS =
  "focus-visible:outline-accent focus-visible:outline-2 focus-visible:outline-offset-2";

/**
 * Dots and a 3 × 4 keypad, from the prototype's PinPad (08-DESIGN §4): the lock
 * screen (T-3.10) and the PIN step (T-3.12). A physical keyboard's digits and
 * Backspace work too while it's on screen.
 */
export function PinPad({
  value,
  onChange,
  onComplete,
  length = 4,
  disabled = false,
  tone = "light",
}: PinPadProps) {
  const chrome = tone === "chrome";

  function press(key: string) {
    if (disabled) return;
    if (key === "delete") {
      onChange(value.slice(0, -1));
      return;
    }
    if (value.length >= length) return;
    const next = value + key;
    onChange(next);
    if (next.length === length) onComplete(next);
  }

  // The latest `press`, so the keyboard listener needn't be re-added each render.
  const pressRef = useRef(press);
  useEffect(() => {
    pressRef.current = press;
  });

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (/^[0-9]$/.test(event.key)) pressRef.current(event.key);
      else if (event.key === "Backspace") pressRef.current("delete");
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className="flex flex-col items-center">
      <div
        role="img"
        aria-label={t("ui.pinProgress", { count: value.length, max: length })}
        className="mb-10 flex gap-3.5"
      >
        {Array.from({ length }, (_, index) => (
          <span
            key={index}
            className={cx(
              "rounded-pill size-3.5 border-[1.5px]",
              index < value.length
                ? "border-accent bg-accent"
                : chrome
                  ? "border-chrome-line"
                  : "border-line",
            )}
          />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3.5">
        {KEYS.map((key, index) =>
          key === "" ? (
            <span key={index} />
          ) : key === "delete" ? (
            <button
              key={key}
              type="button"
              aria-label={t("ui.pinDelete")}
              disabled={disabled}
              onClick={() => press(key)}
              className={cx(
                "rounded-pill flex size-16 items-center justify-center",
                chrome ? "text-chrome-mute" : "text-mute",
                FOCUS,
              )}
            >
              <Icon icon={Delete} size={20} />
            </button>
          ) : (
            <button
              key={key}
              type="button"
              disabled={disabled}
              onClick={() => press(key)}
              className={cx(
                "rounded-pill text-title-1 flex size-16 items-center justify-center border font-normal",
                chrome
                  ? "border-chrome-line text-chrome-ink"
                  : "border-line bg-surface text-ink",
                "disabled:opacity-50",
                FOCUS,
              )}
            >
              {key}
            </button>
          ),
        )}
      </div>
    </div>
  );
}
