import { User } from "lucide-react";

import { ButtonLink } from "@/components/ui/ButtonLink";
import { Icon } from "@/components/ui/Icon";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";
import type { SharedProfile } from "@/lib/queries/profiles";

/**
 * What `/@username` shows someone not signed in (D-544): first name, age,
 * city and main photo, and the way in. Or, when its owner hasn't turned the
 * public link on (or anything else the API refuses), that it isn't public,
 * with nothing of theirs on the page.
 */
export function SharedProfileView({
  shared,
}: {
  shared: SharedProfile | null;
}) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col items-center gap-5 px-4 py-10 text-center">
      {shared ? (
        <>
          <div className="rounded-swipe bg-surface-2 h-80 w-full overflow-hidden">
            {shared.main_photo_url ? (
              // A plain <img>: the CDN isn't configured for next/image.
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={shared.main_photo_url}
                alt=""
                className="size-full object-cover"
              />
            ) : (
              <span className="text-line-strong flex size-full items-center justify-center">
                <Icon icon={User} size={96} />
              </span>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <h1 className="text-title-1 text-ink">
              {shared.age === null
                ? shared.first_name
                : t("profile.nameAge", {
                    name: shared.first_name,
                    age: shared.age,
                  })}
            </h1>
            {shared.city && (
              <p className="text-body text-mute">{shared.city}</p>
            )}
          </div>
          <ButtonLink href="/login">
            {t("share.join", { app: APP_NAME })}
          </ButtonLink>
        </>
      ) : (
        <>
          <h1 className="text-title-1 text-ink">{t("share.unavailable")}</h1>
          <p className="text-body text-mute">
            {t("share.unavailableBody", { app: APP_NAME })}
          </p>
          <ButtonLink href="/login">
            {t("share.join", { app: APP_NAME })}
          </ButtonLink>
        </>
      )}
    </main>
  );
}
