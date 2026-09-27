import { useId, type ComponentPropsWithRef } from "react";

import { cx } from "@/lib/cx";

import { CONTROL, describedBy, FieldFrame } from "./FieldFrame";

type FieldProps = Omit<ComponentPropsWithRef<"input">, "className"> & {
  label: string;
  helper?: string;
  /** Shown instead of the helper, and marks the input invalid. */
  error?: string;
};

/** A labelled text input. Takes every `<input>` prop, `ref` included (React Hook Form's `register`). */
export function Field({ label, helper, error, id, ...input }: FieldProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <FieldFrame id={fieldId} label={label} helper={helper} error={error}>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fieldId, { helper, error })}
        className={cx(CONTROL, "py-3.5")}
        {...input}
      />
    </FieldFrame>
  );
}
