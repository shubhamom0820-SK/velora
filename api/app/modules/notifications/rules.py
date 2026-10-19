"""What a notification is, who it reaches and what its push carries (T-9.4).

Every rule here is an allowlist (CLAUDE.md rule 16): a status that may be told,
the setting that governs each kind's push, the fields each kind's push may
carry, the push services a subscription may name. Anything not listed is
refused or left out, so a new status, kind or field is silent until someone
lists it.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final
from urllib.parse import urlsplit

from app.core.enums import Gender, Role, UserStatus


class Kind(StrEnum):
    MATCH = "match"
    THREAD = "thread"  # someone opened a Thread with you
    MESSAGE = "message"
    LIKE = "like"
    GIFT = "gift"
    ALBUM_REQUEST = "album_request"
    ALBUM_DECIDED = "album_decided"
    KNOT_REQUESTED = "knot_requested"
    KNOT_ACCEPTED = "knot_accepted"
    THREAD_EXPIRING = "thread_expiring"
    LOW_BALANCE = "low_balance"
    # P-72 (D-991, D-994): a person whose possible-minor flags wait for a human.
    MINOR_FLAGS = "minor_flags"


# Only an active account is told anything: a paused one is sent nothing (T-9.6),
# and a frozen, banned or deleted one has nothing to come back to.
TOLD: Final = frozenset({UserStatus.ACTIVE})

# The `notification_prefs` attribute that governs each kind's push. The in-app
# row doesn't follow it: the list is where a turned-off push still shows. None:
# no setting governs it, so an admin can't turn off being told (D-994).
PREF_FOR: Final[Mapping[Kind, str | None]] = {
    Kind.MATCH: "match",
    Kind.THREAD: "message",
    Kind.MESSAGE: "message",
    Kind.LIKE: "like",
    Kind.GIFT: "gift",
    Kind.ALBUM_REQUEST: "album",
    Kind.ALBUM_DECIDED: "album",
    Kind.KNOT_REQUESTED: "knot",
    Kind.KNOT_ACCEPTED: "knot",
    Kind.THREAD_EXPIRING: "expiry",
    Kind.LOW_BALANCE: "balance",
    Kind.MINOR_FLAGS: None,
}

# Kinds with no row in the in-app list (D-852): the chats list is where a
# message shows, and Liked you is where a like does.
PUSH_ONLY: Final = frozenset({Kind.MESSAGE, Kind.LIKE})

# Kinds only a man is told (D-097, D-554, P-460): an hour running out, and a
# balance, which only a man has. An allowlist of who may be told, as
# `threads.rules.sees_the_expiry` is: someone with no gender is told neither.
MEN_ONLY: Final = frozenset({Kind.THREAD_EXPIRING, Kind.LOW_BALANCE})

# Kinds only an admin is told (D-994): written for nobody else, and checked
# again when pushed, so a role taken away in between tells them nothing.
ADMINS_ONLY: Final = frozenset({Kind.MINOR_FLAGS})

# Pushed only while the person has no socket open anywhere (D-854): with one
# open, the app has already shown it.
ONLY_IF_NOT_CONNECTED: Final = frozenset({Kind.MESSAGE})

# What a push may carry, per kind, out of the notification's payload: ids the
# service worker turns into a route, and two flags it turns into words. Never
# an expiry, a price, a balance or a message's text; the name is added apart,
# from `NAMED`, and only without `generic_text`.
PUSHED_FIELDS: Final[Mapping[Kind, tuple[str, ...]]] = {
    Kind.MATCH: ("user_id",),
    Kind.THREAD: ("thread_id", "user_id"),
    Kind.MESSAGE: ("thread_id", "user_id"),
    Kind.LIKE: ("user_id", "super"),
    Kind.GIFT: ("user_id",),
    Kind.ALBUM_REQUEST: ("user_id",),
    Kind.ALBUM_DECIDED: ("user_id", "granted"),
    Kind.KNOT_REQUESTED: ("thread_id", "user_id"),
    Kind.KNOT_ACCEPTED: ("thread_id", "user_id"),
    Kind.THREAD_EXPIRING: ("thread_id",),
    Kind.LOW_BALANCE: (),
    # The person's id only, never `user_id`, which the sender would name and
    # the list would hide across a block: no name, score or image (D-994).
    Kind.MINOR_FLAGS: ("subject_id",),
}

# A push older than this is dropped, not sent: "new message" an hour late is
# noise. Also its Web Push TTL, so a push service holds it no longer either.
PUSH_TTL_S: Final = 60 * 60
# Sends tried before a push is given up on.
PUSH_ATTEMPTS: Final = 3
# A claim older than this is a worker that died mid-send: taken again.
CLAIM_STALE_S: Final = 5 * 60
# A person's push subscriptions kept, newest first: one per browser they use.
SUBSCRIPTIONS_KEPT: Final = 10

# The push services a subscription may name (D-855). The worker POSTs to the
# endpoint the browser gave, so an endpoint anywhere else would make it send
# requests wherever a client chose. Exact hosts, and suffixes after a dot.
PUSH_HOSTS: Final = frozenset(
    {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
)
PUSH_HOST_SUFFIXES: Final = (".push.apple.com", ".notify.windows.com")
ENDPOINT_MAX: Final = 1024


def told(status: UserStatus | None) -> bool:
    return status in TOLD


def reaches(kind: Kind, gender: Gender | None, role: Role | None) -> bool:
    """Whether `kind` may reach someone of `gender` and `role` at all."""
    if kind in ADMINS_ONLY and role is not Role.ADMIN:
        return False
    return kind not in MEN_ONLY or gender is Gender.MALE


def push_host_allowed(endpoint: str) -> bool:
    """`https`, no port, no credentials, and a host on the list."""
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or port is not None or parts.username is not None:
        return False
    if parts.password is not None or not host:
        return False
    return host in PUSH_HOSTS or host.endswith(PUSH_HOST_SUFFIXES)


def push_data(
    kind: Kind, payload: Mapping[str, Any], name: str | None
) -> dict[str, Any]:
    """What a push carries: the kind, its allowed fields, and the name when
    one is given and the kind has a person in it."""
    data: dict[str, Any] = {"kind": str(kind)}
    for field in PUSHED_FIELDS[kind]:
        if field in payload:
            data[field] = payload[field]
    if name is not None and "user_id" in data:
        data["name"] = name
    return data
