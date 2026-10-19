"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { t, type MessageKey } from "@/i18n/t";
import {
  useMinorDecision,
  type AdminMinorFlags,
  type AdminUserDetail,
  type MinorDecision,
} from "@/lib/queries/admin";

import { ConfirmAction } from "./ConfirmAction";

export const MINOR_FLAGS_INTRO: MessageKey = "admin.minorFlags.intro";

/** "2 flags · scores 0.41, 0.93": a model's, two places, never the photo. */
export function flagsText(flags: AdminMinorFlags): string {
  return t("admin.minorFlags.flags", {
    count: flags.flags,
    scores: flags.scores.map((score) => score.toFixed(2)).join(", "),
  });
}

type Choice = {
  decision: MinorDecision;
  label: MessageKey;
  adminOnly: boolean;
};

/**
 * D-991's three decisions, D-1050's who: leaving them and the underage ban
 * are an admin's, a freeze staff's, and only while they can sign in. The API
 * decides; these are the buttons worth showing.
 */
function choicesFor(detail: AdminUserDetail): Choice[] {
  const choices: Choice[] = [
    { decision: "adult", label: "admin.minorFlags.adult", adminOnly: true },
  ];
  const { status, erased } = detail.user;
  if (!erased && (status === "active" || status === "paused")) {
    choices.push({
      decision: "freeze",
      label: "admin.minorFlags.freeze",
      adminOnly: false,
    });
  }
  choices.push({
    decision: "underage",
    label: "admin.minorFlags.underage",
    adminOnly: true,
  });
  return choices;
}

/**
 * A person waiting for a human with possible-minor flags (P-72): the scores,
 * and the decisions staff may make, each behind a reason the audit log keeps.
 * The underage ban says plainly that it can't be undone (D-991).
 */
export function MinorReview({
  detail,
  isAdmin,
}: {
  detail: AdminUserDetail;
  isAdmin: boolean;
}) {
  const [choice, setChoice] = useState<Choice | null>(null);
  const decide = useMinorDecision(detail.user.id);
  const flags = detail.minor_flags;
  if (!flags) return null;
  const choices = choicesFor(detail).filter(
    (each) => isAdmin || !each.adminOnly,
  );

  return (
    <section className="border-accent bg-surface rounded-card flex flex-col gap-2 border p-4">
      <h2 className="text-title-2">{t("admin.minorFlags.waiting")}</h2>
      <p className="text-small text-mute">{t(MINOR_FLAGS_INTRO)}</p>
      <p className="text-body">{flagsText(flags)}</p>
      <div className="flex flex-wrap gap-2">
        {choices.map((each) => (
          <Button
            key={each.decision}
            size="sm"
            variant={each.decision === "adult" ? "ghost" : "danger"}
            onClick={() => {
              decide.reset();
              setChoice(each);
            }}
          >
            {t(each.label)}
          </Button>
        ))}
      </div>
      {choice && (
        <ConfirmAction
          open
          onClose={() => setChoice(null)}
          title={t(choice.label)}
          confirmLabel={t(choice.label)}
          variant={choice.decision === "adult" ? "primary" : "danger"}
          pending={decide.isPending}
          error={decide.error}
          onConfirm={(reason) =>
            decide.mutate(
              { decision: choice.decision, reason },
              { onSuccess: () => setChoice(null) },
            )
          }
        >
          {choice.decision === "underage" && (
            <p role="note" className="text-body text-accent-text">
              {t("admin.minorFlags.underageWarning")}
            </p>
          )}
        </ConfirmAction>
      )}
    </section>
  );
}
