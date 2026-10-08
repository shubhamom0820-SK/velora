"use client";

import { CircleCheck } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { TextArea } from "@/components/ui/TextArea";
import { t, type MessageKey } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { cx } from "@/lib/cx";
import {
  REPORT_DETAILS_MAX,
  type ReportReason,
  useReport,
} from "@/lib/queries/safety";

/** The prototype's six, in its order (`report_reason_t`). */
const REASONS = [
  "fake",
  "scam",
  "harass",
  "sexual",
  "minor",
  "other",
] as const satisfies readonly ReportReason[];

function refusal(error: unknown): MessageKey {
  return error instanceof ApiError && error.code === "RATE_LIMITED"
    ? "profile.reportTooMany"
    : "profile.reportFailed";
}

type ReportSheetProps = {
  open: boolean;
  userId: string;
  firstName: string;
  /** `blocked`: the report blocked them too, so the screen should go. */
  onClose: (blocked: boolean) => void;
};

/**
 * Report someone (T-9.1, 08-DESIGN §5's report sheet): a reason, what they
 * did if she wants to say, and "Also block", on unless she turns it off, as
 * the prototype has it. Sent, it says they're never told who reported them;
 * how soon a moderator looks waits for the moderators' queue (P-761).
 */
export function ReportSheet({
  open,
  userId,
  firstName,
  onClose,
}: ReportSheetProps) {
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [details, setDetails] = useState("");
  const [alsoBlock, setAlsoBlock] = useState(true);
  const report = useReport();
  const errorId = useId();

  function close() {
    const blocked = report.isSuccess && report.variables.also_block;
    report.reset();
    setReason(null);
    setDetails("");
    setAlsoBlock(true);
    onClose(blocked);
  }

  return (
    <Sheet
      open={open}
      onClose={close}
      title={t("profile.reportTitle", { name: firstName })}
    >
      {report.isSuccess ? (
        <section
          role="status"
          className="flex flex-col items-center gap-2 py-2 text-center"
        >
          <Icon icon={CircleCheck} size={28} className="text-accent" />
          <h3 className="text-title-2 text-ink">
            {t("profile.reportSentTitle")}
          </h3>
          <p className="text-small text-mute">{t("profile.reportSentBody")}</p>
          <Button fullWidth onClick={close} className="mt-4">
            {t("profile.reportDone")}
          </Button>
        </section>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (reason === null || report.isPending) return;
            const said = details.trim();
            report.mutate({
              reported_id: userId,
              reason,
              also_block: alsoBlock,
              ...(said ? { details: said } : {}),
            });
          }}
        >
          <p className="text-small text-mute">{t("profile.reportIntro")}</p>
          <fieldset
            className="flex flex-col gap-2"
            aria-describedby={report.isError ? errorId : undefined}
          >
            <legend className="text-small text-mute mb-2">
              {t("profile.reportReasons")}
            </legend>
            {REASONS.map((value) => (
              <label
                key={value}
                className={cx(
                  "rounded-card flex cursor-pointer items-center gap-3 border-[1.5px] px-4 py-3",
                  reason === value
                    ? "border-accent bg-accent-soft"
                    : "border-line",
                )}
              >
                <input
                  type="radio"
                  name="report-reason"
                  value={value}
                  checked={reason === value}
                  onChange={() => setReason(value)}
                  className="accent-accent size-5"
                />
                <span className="text-ui text-ink">
                  {t(`profile.reason.${value}`)}
                </span>
              </label>
            ))}
          </fieldset>
          <TextArea
            label={t("profile.reportDetails")}
            helper={t("profile.reportDetailsHelper")}
            placeholder={t("profile.reportDetailsPlaceholder")}
            maxLength={REPORT_DETAILS_MAX}
            value={details}
            onChange={(event) => setDetails(event.target.value)}
          />
          <label className="rounded-card border-line flex cursor-pointer items-center gap-3 border px-4 py-3">
            <input
              type="checkbox"
              checked={alsoBlock}
              onChange={(event) => setAlsoBlock(event.target.checked)}
              className="accent-accent size-5"
            />
            <span className="text-ui text-ink">
              {t("profile.alsoBlock", { name: firstName })}
            </span>
          </label>
          {report.isError && (
            <p id={errorId} role="alert" className="text-small text-accent">
              {t(refusal(report.error))}
            </p>
          )}
          <Button
            type="submit"
            fullWidth
            disabled={reason === null}
            loading={report.isPending}
          >
            {reason === null
              ? t("profile.reportPick")
              : t("profile.reportSend")}
          </Button>
        </form>
      )}
    </Sheet>
  );
}
