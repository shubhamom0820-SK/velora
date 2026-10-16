"use client";

import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/Button";
import type { ButtonVariant } from "@/components/ui/buttonClasses";
import { Sheet } from "@/components/ui/Sheet";
import { TextArea } from "@/components/ui/TextArea";
import { t } from "@/i18n/t";

import { refusalText } from "./refusal";

/** The API's bounds on a reason (`admin.rules`, D-921). */
export const REASON_MIN = 10;
export const REASON_MAX = 500;

type ConfirmActionProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  confirmLabel: string;
  variant?: ButtonVariant;
  pending: boolean;
  error: unknown;
  /** Called with the reason, trimmed, once it is long enough. */
  onConfirm: (reason: string) => void;
  /** Anything else the action asks for, above the reason: a choice, a number. */
  children?: ReactNode;
  /** False while what `children` asks for isn't ready. */
  ready?: boolean;
};

/**
 * Every staff action behind a confirmation (T-9.5): a sheet that asks why,
 * in at least 10 characters, which the audit log keeps (D-921), and says why
 * the API refused, if it did. The button is busy while the call runs, so a
 * double tap can't send it twice.
 */
export function ConfirmAction({
  open,
  onClose,
  title,
  confirmLabel,
  variant = "danger",
  pending,
  error,
  onConfirm,
  children,
  ready = true,
}: ConfirmActionProps) {
  const [reason, setReason] = useState("");
  const trimmed = reason.trim();
  const enough = trimmed.length >= REASON_MIN;

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <div className="flex flex-col gap-2">
          {error !== null && error !== undefined && (
            <p role="alert" className="text-small text-accent">
              {refusalText(error)}
            </p>
          )}
          <Button
            variant={variant}
            fullWidth
            loading={pending}
            disabled={!enough || !ready}
            onClick={() => onConfirm(trimmed)}
          >
            {confirmLabel}
          </Button>
          <Button variant="ghost" fullWidth onClick={onClose}>
            {t("admin.confirm.cancel")}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        {children}
        <TextArea
          label={t("admin.confirm.reason")}
          helper={t("admin.confirm.reasonHelper")}
          maxLength={REASON_MAX}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
    </Sheet>
  );
}
