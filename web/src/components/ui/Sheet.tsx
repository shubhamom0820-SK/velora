"use client";

import { X } from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

import { t } from "@/i18n/t";

import { Icon } from "./Icon";

type SheetProps = {
  open: boolean;
  onClose: () => void;
  /** Names the dialog for screen readers, and heads the sheet. */
  title: string;
  /** The scrolling body. */
  children: ReactNode;
  /** Stays put below the body, e.g. the confirm button. */
  footer?: ReactNode;
};

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * A modal sheet: from the bottom on mobile, centred from 768 px. Focus moves
 * into it and can't Tab out; Esc, ✕ and the backdrop close it, and focus goes
 * back to whatever opened it.
 */
export function Sheet({ open, onClose, title, children, footer }: SheetProps) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const opener =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    // The dialog itself takes focus, so a screen reader reads its title first.
    panel.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      opener?.focus();
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      // A sheet opened from a sheet closes alone.
      event.stopPropagation();
      onClose();
      return;
    }
    const box = panel.current;
    if (event.key !== "Tab" || !box) return;
    event.stopPropagation();
    const items = Array.from(box.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = items[0];
    const last = items.at(-1);
    const current = document.activeElement;
    if (!first || !last) {
      event.preventDefault();
    } else if (event.shiftKey && (current === first || current === box)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && current === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-40 flex flex-col justify-end md:items-center md:justify-center md:p-6">
      <div
        aria-hidden
        onClick={onClose}
        className="bg-scrim absolute inset-0 motion-safe:animate-fade-in"
      />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="rounded-t-sheet border-line bg-surface animate-sheet-up md:rounded-sheet relative mx-auto flex max-h-[88dvh] w-full max-w-130 flex-col border-t outline-none motion-reduce:animate-fade-in md:animate-fade-in md:border"
      >
        <div
          aria-hidden
          className="rounded-pill bg-line mx-auto mt-4 h-1 w-9 shrink-0 md:hidden"
        />
        <div className="flex items-center gap-3 pt-2 pr-2 pl-5 md:pt-4">
          <h2 id={titleId} className="text-title-2 text-ink flex-1">
            {title}
          </h2>
          <button
            type="button"
            aria-label={t("ui.close")}
            onClick={onClose}
            className="rounded-pill text-mute focus-visible:outline-accent flex size-11 items-center justify-center focus-visible:outline-2"
          >
            <Icon icon={X} size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 pt-2 pb-6">{children}</div>
        {footer && (
          <div className="border-line border-t px-5 pt-4 pb-6">{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  );
}
