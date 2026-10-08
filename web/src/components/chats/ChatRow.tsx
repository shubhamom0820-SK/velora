import { Link2, Trash2 } from "lucide-react";
import Link from "next/link";

import { Avatar } from "@/components/ui/Avatar";
import { Countdown } from "@/components/ui/Countdown";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { cx } from "@/lib/cx";
import type { ThreadRow } from "@/lib/queries/threads";

type ChatRowProps = {
  row: ThreadRow;
  /** He sees the countdown; she never does (D-097, D-554, P-460). */
  man: boolean;
  selecting: boolean;
  selected: boolean;
  /** Select mode can't take this one: the cap is reached and it isn't chosen. */
  selectDisabled: boolean;
  onToggle: () => void;
  onClear: () => void;
};

function preview(row: ThreadRow): string {
  const last = row.last_message;
  if (!last) return t("chats.noMessages");
  // A voice note carries no text: the web names it (T-7.2).
  if (last.kind === "voice") return t("chats.voiceNote");
  return last.text ?? "";
}

/**
 * One chat (08-DESIGN §8): a 48 px avatar with the online dot, the name, a knot
 * glyph on a Knot, the last message, an unread dot, and, on his Threads alone,
 * the countdown pill. Her rows draw no countdown and no expired state, whatever
 * `status` says (P-460): nothing here reads time for her. Tapping opens the
 * Thread (`/chats/[id]`, T-7.11); in select mode it chooses the row instead.
 * Their text is React's to escape, never set as HTML.
 */
export function ChatRow({
  row,
  man,
  selecting,
  selected,
  selectDisabled,
  onToggle,
  onClear,
}: ChatRowProps) {
  const other = row.other;
  const name = other.deleted
    ? t("chats.deletedAccount")
    : (other.first_name ?? "");
  const knotted = row.status === "knotted";
  const countdown =
    man && !knotted && row.expires_at !== null ? row.expires_at : null;

  const body = (
    <>
      <Avatar
        name={name}
        src={other.main_photo_url ?? undefined}
        size={48}
        online={other.is_online}
        verified={other.shows_badge}
      />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-1.5">
          <span
            className={cx(
              "text-ui truncate",
              other.deleted ? "text-mute" : "text-ink",
            )}
          >
            {name}
          </span>
          {knotted && (
            <Icon
              icon={Link2}
              size={14}
              label={t("chats.knot")}
              className="text-accent"
            />
          )}
          {row.unread > 0 && (
            <span
              role="img"
              aria-label={t(
                row.unread === 1 ? "chats.unread.one" : "chats.unread.other",
                { count: row.unread },
              )}
              className="rounded-pill bg-accent size-2 shrink-0"
            />
          )}
        </span>
        <span className="text-small text-mute truncate">{preview(row)}</span>
      </span>
      {countdown !== null && <Countdown expiresAt={countdown} />}
    </>
  );

  return (
    <li
      className={cx(
        "border-line flex items-center gap-3 border-b px-(--shell-gutter) py-3",
        selected && "bg-accent-soft",
      )}
    >
      {selecting ? (
        <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={selected}
            disabled={selectDisabled}
            onChange={onToggle}
            aria-label={t("chats.selectRow", { name })}
            className="accent-accent size-5 shrink-0"
          />
          {body}
        </label>
      ) : (
        <>
          <Link
            href={`/chats/${row.id}`}
            className="flex min-w-0 flex-1 items-center gap-3"
          >
            {body}
          </Link>
          <button
            type="button"
            onClick={onClear}
            aria-label={t("chats.clearRow", { name })}
            className="text-mute hover:text-ink focus-visible:outline-accent rounded-pill relative p-2 before:absolute before:-inset-1 focus-visible:outline-2"
          >
            <Icon icon={Trash2} size={18} />
          </button>
        </>
      )}
    </li>
  );
}
