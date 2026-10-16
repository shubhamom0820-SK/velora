"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/Button";
import { TextArea } from "@/components/ui/TextArea";
import { t } from "@/i18n/t";
import { useAdminThread } from "@/lib/queries/admin";

import { AdminList } from "./AdminList";
import { REASON_MAX, REASON_MIN } from "./ConfirmAction";
import { entryTime } from "./time";

/**
 * A chat as staff read it (D-924): asked only once they have said why, which
 * the audit log keeps with each page read; every message, what either person
 * cleared included (T-7.8), as written where masking changed it. A report's
 * link starts the reason with the report.
 */
export function ThreadReader({
  id,
  reportId,
}: {
  id: string;
  reportId?: string;
}) {
  const [typed, setTyped] = useState(reportId ? `Report ${reportId}: ` : "");
  const [reason, setReason] = useState<string | null>(null);
  const messages = useAdminThread(id, reason);
  const trimmed = typed.trim();

  function read(event: FormEvent) {
    event.preventDefault();
    if (trimmed.length >= REASON_MIN) setReason(trimmed);
  }

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-title-1">{t("admin.thread.title")}</h1>
      {reason === null ? (
        <form onSubmit={read} className="flex flex-col gap-3">
          <TextArea
            label={t("admin.thread.reason")}
            helper={t("admin.confirm.reasonHelper")}
            maxLength={REASON_MAX}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
          />
          <Button type="submit" disabled={trimmed.length < REASON_MIN}>
            {t("admin.thread.read")}
          </Button>
        </form>
      ) : (
        <AdminList
          query={messages}
          empty={t("admin.thread.empty")}
          keyOf={(m) => m.id}
        >
          {(message) => (
            <div className="border-line bg-surface rounded-card flex flex-col gap-1 border p-3">
              <span className="text-micro text-mute">
                {message.sender_id} ·{" "}
                {entryTime.format(new Date(message.created_at))}
              </span>
              {message.kind === "voice" ? (
                <>
                  <span className="text-small">
                    {t("admin.thread.voice", {
                      seconds: message.duration_s ?? 0,
                    })}
                  </span>
                  {message.audio_url && (
                    <audio controls preload="none" src={message.audio_url} />
                  )}
                </>
              ) : (
                <p className="text-body whitespace-pre-wrap">{message.body}</p>
              )}
              {message.masked && (
                <span className="text-micro text-accent">
                  {t("admin.thread.masked")}
                </span>
              )}
            </div>
          )}
        </AdminList>
      )}
    </section>
  );
}
