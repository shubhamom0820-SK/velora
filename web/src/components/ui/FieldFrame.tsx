import type { ReactNode } from "react";

/** The box every text control shares: Field and TextArea. */
export const CONTROL =
  "w-full rounded-input border border-line bg-surface px-4 text-input text-ink placeholder:text-mute focus:border-accent aria-invalid:border-accent disabled:bg-surface-2 disabled:text-mute";

type Messages = { helper?: string; error?: string; counter?: string };

/** The ids a control's `aria-describedby` lists: its error (or helper) and its counter. */
export function describedBy(
  id: string,
  { helper, error, counter }: Messages,
): string | undefined {
  const ids = [
    error ? `${id}-error` : helper ? `${id}-helper` : null,
    counter ? `${id}-counter` : null,
  ].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}

type FieldFrameProps = Messages & {
  id: string;
  label: string;
  children: ReactNode;
};

/** Label above, then the control, then the error (which replaces the helper) and counter. */
export function FieldFrame({
  id,
  label,
  helper,
  error,
  counter,
  children,
}: FieldFrameProps) {
  const message = error ?? helper;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-small text-mute">
        {label}
      </label>
      {children}
      {(message || counter) && (
        <div className="text-small flex items-start justify-between gap-3">
          {message ? (
            <p
              id={error ? `${id}-error` : `${id}-helper`}
              className={error ? "text-accent" : "text-mute"}
            >
              {message}
            </p>
          ) : (
            <span />
          )}
          {counter && (
            <p id={`${id}-counter`} className="text-mute shrink-0 tabular-nums">
              {counter}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
