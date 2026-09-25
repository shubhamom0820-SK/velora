"""The database's enum types, as Python enums.

One class per Postgres enum in 03-SCHEMA.md, shared across modules (`Gender` is
used by users, profiles and discovery alike). Member order matches the database:
Postgres sorts and compares enum values by declared position.

The migration that creates these types hardcodes its own values, so it stays
frozen in time. tests/core/test_enums.py fails if the two ever disagree —
Alembic's model comparison does not look at enum values, so nothing else would.
"""

from __future__ import annotations

from enum import StrEnum


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class Seeking(StrEnum):
    WOMEN = "women"
    MEN = "men"
    EVERYONE = "everyone"


class Intent(StrEnum):
    SERIOUS = "serious"
    LONGTERM = "longterm"
    SHORT = "short"
    ONENIGHT = "onenight"
    CHAT = "chat"
    DISCREET = "discreet"


class OnboardingStep(StrEnum):
    DOB = "dob"
    GENDER = "gender"
    SEEKING = "seeking"
    PROFILE = "profile"
    USERNAME = "username"
    ABOUT = "about"
    PHOTOS = "photos"
    INTERESTS = "interests"
    PIN = "pin"
    SELFIE = "selfie"
    DONE = "done"


class UserStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    FROZEN = "frozen"
    BANNED = "banned"
    DELETED = "deleted"


class Role(StrEnum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class PhotoKind(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    SELFIE = "selfie"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SwipeDirection(StrEnum):
    LIKE = "like"
    PASS = "pass"
    SUPER = "super"


class ThreadStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    KNOTTED = "knotted"


class ThreadOrigin(StrEnum):
    MATCH = "match"
    DM = "dm"


class MessageKind(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    SYSTEM = "system"


class AlbumRequestStatus(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    DECLINED = "declined"
    REVOKED = "revoked"


class ReportReason(StrEnum):
    FAKE = "fake"
    SCAM = "scam"
    HARASS = "harass"
    SEXUAL = "sexual"
    MINOR = "minor"
    OTHER = "other"


class ReportStatus(StrEnum):
    OPEN = "open"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class Kudos(StrEnum):
    GREAT_CONVERSATION = "great_conversation"
    GENUINELY_FUNNY = "genuinely_funny"
    EASY_TO_TALK_TO = "easy_to_talk_to"
    REALLY_THOUGHTFUL = "really_thoughtful"


class LedgerReason(StrEnum):
    PURCHASE = "purchase"
    PURCHASE_BONUS = "purchase_bonus"
    REFERRAL_REWARD = "referral_reward"
    ADMIN_GRANT = "admin_grant"
    REFUND = "refund"
    GIFT = "gift"
    REFUND_BANNED_PARTNER = "refund_banned_partner"
    REFUND_ALBUM_DECLINED = "refund_album_declined"
    THREAD_OPEN = "thread_open"
    DM_OPEN = "dm_open"
    THREAD_REOPEN = "thread_reopen"
    VOICE_UNLOCK = "voice_unlock"
    ALBUM_REQUEST = "album_request"
    SUPER_LIKE = "super_like"
    LIKED_YOU_REVEAL = "liked_you_reveal"


class PaymentStatus(StrEnum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class FraudBand(StrEnum):
    NORMAL = "normal"
    MONITOR = "monitor"
    SHADOW = "shadow"
    FREEZE = "freeze"


class BanKind(StrEnum):
    PHONE_HASH = "phone_hash"
    DEVICE_ID = "device_id"


# Postgres type name -> Python enum. Models declare their columns with these
# names (`sa.Enum(Gender, name="gender_t", create_type=False)`); the types
# themselves are created by migration, never by SQLAlchemy.
PG_ENUMS: dict[str, type[StrEnum]] = {
    "gender_t": Gender,
    "seeking_t": Seeking,
    "intent_t": Intent,
    "onboarding_t": OnboardingStep,
    "user_status_t": UserStatus,
    "role_t": Role,
    "photo_kind_t": PhotoKind,
    "review_status_t": ReviewStatus,
    "swipe_dir_t": SwipeDirection,
    "thread_status_t": ThreadStatus,
    "thread_origin_t": ThreadOrigin,
    "msg_kind_t": MessageKind,
    "album_req_t": AlbumRequestStatus,
    "report_reason_t": ReportReason,
    "report_status_t": ReportStatus,
    "kudos_t": Kudos,
    "ledger_reason_t": LedgerReason,
    "payment_status_t": PaymentStatus,
    "fraud_band_t": FraudBand,
    "ban_kind_t": BanKind,
}
