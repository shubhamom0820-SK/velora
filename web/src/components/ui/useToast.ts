import { use } from "react";

import { ToastContext } from "./ToastProvider";

/** `const toast = useToast(); toast.show({ message, tone, action })`. */
export function useToast() {
  const api = use(ToastContext);
  if (!api) {
    throw new Error("useToast needs a <ToastProvider> above it.");
  }
  return api;
}
