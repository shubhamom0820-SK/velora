"use client";

import { Ban, Ellipsis, Flag, Share2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

import { BlockSheet } from "./BlockSheet";
import { ReportSheet } from "./ReportSheet";

type Open = "menu" | "report" | "block" | null;

/**
 * The profile's ⋯ menu (08-DESIGN §8). It shares the profile's link,
 * `/@username` (D-001), which opens the in-app profile for anyone signed in,
 * and shows its page to anyone else only when its owner turned their public
 * link on (D-544). On someone else's profile it reports and blocks them
 * (T-9.1, P-442); once they're blocked, the profile is left for the screen
 * before it, or Discover, since it is gone for both (D-862).
 */
export function ProfileMenu({
  userId,
  username,
  firstName,
  own,
}: {
  userId: string;
  username: string;
  firstName: string;
  own: boolean;
}) {
  const toast = useToast();
  const router = useRouter();
  const [open, setOpen] = useState<Open>(null);

  async function share() {
    const url = `${window.location.origin}/@${username}`;
    const text = t("profile.shareText", { name: firstName, app: APP_NAME });
    setOpen(null);
    try {
      if (typeof navigator.share === "function") {
        await navigator.share({ url, text });
        return;
      }
      await navigator.clipboard.writeText(url);
      toast.show({ message: t("profile.copied") });
    } catch (error) {
      // A person closing the share sheet isn't a failure.
      if (error instanceof DOMException && error.name === "AbortError") return;
      toast.show({ message: t("profile.copyFailed"), tone: "error" });
    }
  }

  function gone() {
    setOpen(null);
    toast.show({ message: t("profile.blocked", { name: firstName }) });
    if (window.history.length > 1) router.back();
    else router.replace("/discover");
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen("menu")}
        className="bg-surface text-ink rounded-pill shadow-1 flex size-10 items-center justify-center"
      >
        <Icon icon={Ellipsis} size={20} label={t("profile.more")} />
      </button>
      <Sheet
        open={open === "menu"}
        onClose={() => setOpen(null)}
        title={t("profile.more")}
      >
        <div className="flex flex-col gap-1">
          <Button
            variant="ghost"
            onClick={() => void share()}
            className="w-full"
          >
            <Icon icon={Share2} size={18} />
            {t("profile.share")}
          </Button>
          {!own && (
            <>
              <Button
                variant="ghost"
                onClick={() => setOpen("report")}
                className="text-accent w-full"
              >
                <Icon icon={Flag} size={18} />
                {t("profile.report")}
              </Button>
              <Button
                variant="ghost"
                onClick={() => setOpen("block")}
                className="text-accent w-full"
              >
                <Icon icon={Ban} size={18} />
                {t("profile.block", { name: firstName })}
              </Button>
            </>
          )}
        </div>
      </Sheet>
      {!own && (
        <>
          <ReportSheet
            open={open === "report"}
            userId={userId}
            firstName={firstName}
            onClose={(blocked) => (blocked ? gone() : setOpen(null))}
          />
          <BlockSheet
            open={open === "block"}
            userId={userId}
            firstName={firstName}
            onClose={() => setOpen(null)}
            onBlocked={gone}
          />
        </>
      )}
    </>
  );
}
