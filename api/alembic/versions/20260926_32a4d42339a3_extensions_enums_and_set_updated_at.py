"""extensions, enums and set_updated_at

Revision ID: 32a4d42339a3
Revises:
Create Date: 2026-09-26 02:45:45.335611

The foundation every later schema migration builds on (03-SCHEMA.md, T-1.8):
the four extensions, all 20 enum types, and the trigger function that keeps
`updated_at` current on every mutable table.

Enum values are written out here rather than imported from app/core/enums.py:
a migration must be frozen in time, so a later change to the Python enums can
never change what this revision does. tests/core/test_enums.py checks the two
agree.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "32a4d42339a3"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTENSIONS = ("postgis", "pg_trgm", "pgcrypto", "citext")

# In 03-SCHEMA.md order. Values are order-sensitive: Postgres sorts and compares
# enum values by their declared position.
ENUMS: dict[str, tuple[str, ...]] = {
    "gender_t": ("male", "female"),
    "seeking_t": ("women", "men", "everyone"),
    "intent_t": ("serious", "longterm", "short", "onenight", "chat", "discreet"),
    "onboarding_t": (
        "dob",
        "gender",
        "seeking",
        "profile",
        "username",
        "about",
        "photos",
        "interests",
        "pin",
        "selfie",
        "done",
    ),
    "user_status_t": ("active", "paused", "frozen", "banned", "deleted"),
    "role_t": ("user", "moderator", "admin"),
    "photo_kind_t": ("public", "private", "selfie"),
    "review_status_t": ("pending", "approved", "rejected"),
    "swipe_dir_t": ("like", "pass", "super"),
    "thread_status_t": ("active", "expired", "knotted"),
    "thread_origin_t": ("match", "dm"),
    "msg_kind_t": ("text", "voice", "system"),
    "album_req_t": ("pending", "granted", "declined", "revoked"),
    "report_reason_t": ("fake", "scam", "harass", "sexual", "minor", "other"),
    "report_status_t": ("open", "actioned", "dismissed"),
    "kudos_t": (
        "great_conversation",
        "genuinely_funny",
        "easy_to_talk_to",
        "really_thoughtful",
    ),
    "ledger_reason_t": (
        "purchase",
        "purchase_bonus",
        "referral_reward",
        "admin_grant",
        "refund",
        "gift",
        "refund_banned_partner",
        "refund_album_declined",
        "thread_open",
        "dm_open",
        "thread_reopen",
        "voice_unlock",
        "album_request",
        "super_like",
        "liked_you_reveal",
    ),
    "payment_status_t": ("created", "paid", "failed", "refunded"),
    "fraud_band_t": ("normal", "monitor", "shadow", "freeze"),
    "ban_kind_t": ("phone_hash", "device_id"),
}

# now() is the transaction's start time, by design: every row a transaction
# touches gets the same timestamp. Rule 7 (core.clock) governs Python code, not
# database defaults and triggers.
SET_UPDATED_AT = """
create function set_updated_at() returns trigger
language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end;
$$
"""


def upgrade() -> None:
    """Upgrade schema."""
    for name in EXTENSIONS:
        op.execute(sa.text(f"create extension if not exists {name}"))

    for name, values in ENUMS.items():
        labels = ", ".join(f"'{value}'" for value in values)
        op.execute(sa.text(f"create type {name} as enum ({labels})"))

    op.execute(sa.text(SET_UPDATED_AT))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("drop function set_updated_at()"))

    for name in reversed(ENUMS):
        op.execute(sa.text(f"drop type {name}"))

    for name in reversed(EXTENSIONS):
        op.execute(sa.text(f"drop extension {name}"))
