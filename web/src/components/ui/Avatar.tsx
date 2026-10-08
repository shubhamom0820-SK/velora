import { Check } from "lucide-react";

import { t } from "@/i18n/t";

import { Icon } from "./Icon";

type AvatarProps = {
  name: string;
  /** Photo URL. Without one, the initial shows on the accent-to-chrome gradient. */
  src?: string;
  /** Diameter in px; the prototype uses 46 in lists and 50 in chats. */
  size?: number;
  online?: boolean;
  /** The badge (D-393, T-4.12): the selfie matched the face photo **and** a
   * shown photo's face matched the selfie, as the server computes it (T-6.2's
   * `Card`), never raw `is_verified`. A tick in `--accent` (the founder's
   * choice, 7 October 2026); the words say only "Selfie matched", never
   * "Verified" (D-262), and a shield stays rejected. */
  verified?: boolean;
};

/** A round profile picture, named for screen readers with its online and selfie-matched states. */
export function Avatar({
  name,
  src,
  size = 46,
  online = false,
  verified = false,
}: AvatarProps) {
  const label = [
    name,
    online && t("ui.online"),
    verified && t("ui.selfieMatched"),
  ]
    .filter(Boolean)
    .join(", ");
  const initial = Array.from(name.trim())[0]?.toUpperCase() ?? "";

  return (
    <span
      role="img"
      aria-label={label}
      className="relative inline-flex shrink-0"
      style={{ width: size, height: size }}
    >
      {src ? (
        // A plain <img>: next/image needs the photo host configured, which
        // arrives with uploads (T-4.x).
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="rounded-pill size-full object-cover" />
      ) : (
        <span
          aria-hidden
          className="rounded-pill from-accent to-chrome text-title-2 text-on-accent flex size-full items-center justify-center bg-linear-to-br"
        >
          {initial}
        </span>
      )}
      {online && (
        <span
          aria-hidden
          className="rounded-pill border-surface bg-accent absolute right-0 bottom-0 size-3 border-2"
        />
      )}
      {verified && (
        <span
          aria-hidden
          className="rounded-pill bg-surface text-accent absolute -top-0.5 -right-0.5 flex size-[18px] items-center justify-center"
        >
          <Icon icon={Check} size={12} />
        </span>
      )}
    </span>
  );
}
