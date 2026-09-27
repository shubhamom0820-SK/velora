"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Toast, type ToastAction, type ToastTone } from "./Toast";

export type ToastOptions = {
  message: string;
  tone?: ToastTone;
  /** A button in the toast, e.g. Undo. Pressing it also dismisses the toast. */
  action?: ToastAction;
  durationMs?: number;
};

type ToastApi = {
  /** Shows a toast, replacing any that is showing: one at a time, as in the prototype. */
  show: (options: ToastOptions) => void;
  dismiss: () => void;
};

export const ToastContext = createContext<ToastApi | null>(null);

/** Long enough to read a line and reach Undo. */
const TOAST_MS = 5000;

/** Holds the one toast on screen. Mounted once, in the root layout. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<(ToastOptions & { id: number }) | null>(
    null,
  );
  const lastId = useRef(0);

  const dismiss = useCallback(() => setToast(null), []);
  const show = useCallback((options: ToastOptions) => {
    lastId.current += 1;
    setToast({ ...options, id: lastId.current });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(dismiss, toast.durationMs ?? TOAST_MS);
    return () => clearTimeout(timer);
  }, [toast, dismiss]);

  const api = useMemo(() => ({ show, dismiss }), [show, dismiss]);
  const tone = toast?.tone ?? "info";
  const shown = toast && (
    <Toast
      key={toast.id}
      message={toast.message}
      tone={tone}
      action={toast.action}
      onDismiss={dismiss}
    />
  );

  return (
    <ToastContext value={api}>
      {children}
      {/* Both regions stay mounted so screen readers announce what appears in them. */}
      <div className="pointer-events-none fixed inset-x-0 top-18 z-50 flex justify-center px-6">
        <div role="status">{tone === "info" && shown}</div>
        <div role="alert">{tone === "error" && shown}</div>
      </div>
    </ToastContext>
  );
}
