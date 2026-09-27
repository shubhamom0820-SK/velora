"use client";

import {
  useId,
  useState,
  type ChangeEvent,
  type ComponentPropsWithRef,
} from "react";

import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";

import { CONTROL, describedBy, FieldFrame } from "./FieldFrame";

type TextAreaProps = Omit<ComponentPropsWithRef<"textarea">, "className"> & {
  label: string;
  helper?: string;
  /** Shown instead of the helper, and marks the textarea invalid. */
  error?: string;
  /** Caps the length and shows a `12/300` counter. */
  maxLength?: number;
};

/** A labelled multi-line input with an optional character counter. */
export function TextArea({
  label,
  helper,
  error,
  id,
  maxLength,
  value,
  defaultValue,
  onChange,
  rows = 4,
  ...rest
}: TextAreaProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const [typed, setTyped] = useState(() => String(defaultValue ?? "").length);
  const length = value === undefined ? typed : String(value).length;
  const counter =
    maxLength === undefined
      ? undefined
      : t("ui.counter", { count: length, max: maxLength });

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setTyped(event.target.value.length);
    onChange?.(event);
  }

  return (
    <FieldFrame
      id={fieldId}
      label={label}
      helper={helper}
      error={error}
      counter={counter}
    >
      <textarea
        id={fieldId}
        rows={rows}
        maxLength={maxLength}
        value={value}
        defaultValue={defaultValue}
        onChange={handleChange}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fieldId, { helper, error, counter })}
        className={cx(CONTROL, "resize-none py-3")}
        {...rest}
      />
    </FieldFrame>
  );
}
