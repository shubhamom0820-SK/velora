"use client";

import { Ellipsis, Share2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/useToast";
import { t } from "@/i18n/t";
import { APP_NAME } from "@/lib/app";

/**
 * The profile's ⋯ menu (08-DESIGN §8). Today it shares the profile's link,
 * `/@username` (D-001); Report and Block join it with T-9.1 (P-442). The
 * link opens the in-app profile for anyone signed in, and shows its page to
 * anyone else only when its owner turned their public link on (D-544).
 */
export function ProfileMenu({
  username,
  firstName,
}: {
  username: string;
  firstName: string;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);

  async function share() {
    const url = `${window.location.origin}/@${username}`;
    const text = t("profile.shareText", { name: firstName, app: APP_NAME });
    setOpen(false);
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

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="bg-surface text-ink rounded-pill shadow-1 flex size-10 items-center justify-center"
      >
        <Icon icon={Ellipsis} size={20} label={t("profile.more")} />
      </button>
      <Sheet
        open={open}
        onClose={() => setOpen(false)}
        title={t("profile.more")}
      >
        <Button variant="ghost" onClick={() => void share()} className="w-full">
          <Icon icon={Share2} size={18} />
          {t("profile.share")}
        </Button>
      </Sheet>
    </>
  );
}
