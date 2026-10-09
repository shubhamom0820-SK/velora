"""What erasing a deleted account takes, and what it keeps (T-9.6, D-051, D-503).

Every column holding a key to `users` is in exactly one of the two lists below:
the erasure deletes the rows naming the user in an `ERASED` column, and leaves
every `KEPT` one. Tests hold this to the database, so a table or column added
later fails CI, naming D-503, until someone decides which it is.

D-051 decides the split: erased is the profile, photos, private album and
everything else other people can see of the person, and whatever only served
the account itself; kept is the ledger and payments, reports and moderation
records, messages, and anything another person holds or paid for. The `users`
row itself stays, anonymised (`repository.anonymise`), since kept rows name it.

This is not D-072's list. An under-18 refusal happens at the dob step, before
anything rule 12 keeps can exist, and deletes everything; the erasure happens
to an account that may have lived for years, and keeps what moderation and
money need.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.modules.account.models import DataExport
from app.modules.album.models import AlbumCopy
from app.modules.auth.models import Session
from app.modules.discovery.models import ProfileView
from app.modules.kudos.models import Kudos
from app.modules.matches.models import Match
from app.modules.messages.models import MessageUnlock
from app.modules.notifications.models import (
    Notification,
    NotificationPrefs,
    PushOutbox,
    PushSubscription,
)
from app.modules.photos.models import Photo
from app.modules.profiles.models import Profile, ProfileIntent, ProfileInterest
from app.modules.safety.models import Block
from app.modules.swipes.models import LikedYouReveal, Swipe
from app.modules.threads.models import ThreadClear
from app.modules.verification.models import Verification


@dataclass(frozen=True)
class Erased:
    """Rows of `model` naming the user in any of `columns` are deleted."""

    model: type[Any]
    columns: tuple[str, ...]


# In an order the keys between them allow: verifications and album copies before
# photos.
ERASED = (
    Erased(Profile, ("user_id",)),
    Erased(ProfileIntent, ("user_id",)),
    Erased(ProfileInterest, ("user_id",)),
    Erased(Verification, ("user_id",)),
    # Their private photos watermarked for others, and others' watermarked for
    # them (T-8.4, D-730): before photos, whose rows they name.
    Erased(AlbumCopy, ("owner_id", "viewer_id")),
    Erased(Photo, ("user_id",)),
    Erased(DataExport, ("user_id",)),
    # Who they liked, passed, viewed and revealed, and who did so to them:
    # nobody sees an erased person in a list again.
    Erased(Swipe, ("swiper_id", "target_id")),
    Erased(LikedYouReveal, ("viewer_id", "liker_id")),
    Erased(ProfileView, ("viewer_id", "viewed_id")),
    Erased(Match, ("user_low", "user_high")),
    # Their own: whom they blocked, chats they cleared, voice notes they
    # unlocked (the ledger keeps the payment), kudos on their profile.
    Erased(Block, ("blocker_id",)),
    Erased(ThreadClear, ("user_id",)),
    Erased(MessageUnlock, ("user_id",)),
    Erased(Kudos, ("to_id",)),
    Erased(Notification, ("user_id",)),
    Erased(NotificationPrefs, ("user_id",)),
    Erased(PushSubscription, ("user_id",)),
    Erased(PushOutbox, ("user_id",)),
    Erased(Session, ("user_id",)),
)

# (table, column) → why the rows stay.
KEPT: dict[tuple[str, str], str] = {
    ("ledger_entries", "user_id"): "rule 12; money, detached from identity",
    ("payments", "user_id"): "rule 12; money",
    ("refund_requests", "user_id"): "a payment's record",
    (
        "wallets",
        "user_id",
    ): "the balance the ledger sums to (T-9.9); lost, not refunded (D-504)",
    ("messages", "sender_id"): "rule 12; shown as from “Deleted account” (D-051)",
    ("threads", "user_low"): "the other person's chat, and the messages' thread",
    ("threads", "user_high"): "the other person's chat, and the messages' thread",
    ("threads", "opened_by"): "the other person's chat, and the messages' thread",
    ("reports", "reporter_id"): "rule 12; moderation",
    ("reports", "reported_id"): "rule 12; moderation",
    ("reports", "resolved_by"): "rule 12; moderation",
    ("audit_log", "actor_id"): "rule 12; what staff did",
    ("fraud_scores", "user_id"): "moderation records (D-051)",
    ("fraud_events", "user_id"): "moderation records (D-051)",
    (
        "blocks",
        "blocked_id",
    ): "the other person's block: theirs, not the erased person's",
    (
        "kudos",
        "from_id",
    ): "kudos the other person earned stay theirs, from nobody named",
    ("gift_sends", "sender_id"): "a paid action's record (the ledger names it)",
    ("gift_sends", "recipient_id"): "a paid action's record (the ledger names it)",
    ("album_requests", "requester_id"): "a paid action's record (the ledger names it)",
    ("album_requests", "owner_id"): "a paid action's record (the ledger names it)",
    ("referrals", "referee_id"): "a reward's record (the ledger names it)",
    ("referrals", "referrer_id"): "a reward's record (the ledger names it)",
    # T-8.11 (D-470, P-371): the number's welcome, so a later account on it,
    # after this erasure, gets none. Append-only besides.
    ("welcome_grants", "user_id"): "one welcome per number, ever (D-470)",
}

# Kept tables a planned task builds, named now so the erasure can never be
# changed to clear them without someone reading why. Each leaves this list for
# KEPT when its table exists, or the check names it.
# T-8.11's `welcome_grants` was the first, and is in KEPT since it was built.
KEPT_WHEN_BUILT: dict[str, str] = {}

# Every stored file behind an erased row, deleted and read back before the
# rows go. A test holds it to the schema: every `*_key` column on an erased
# table is here.
FILES: tuple[tuple[type[Any], str, Literal["public", "private"]], ...] = (
    (Photo, "raw_key", "private"),
    (Photo, "public_key", "public"),
    (Photo, "scored_key", "private"),
    (Photo, "blur_key", "public"),
    (DataExport, "file_key", "private"),
    (AlbumCopy, "file_key", "private"),
)


def columns_of(model: type[Any]) -> tuple[str, ...]:
    """The columns naming the user on `model`'s rows, as `ERASED` lists them."""
    return next(e.columns for e in ERASED if e.model is model)
