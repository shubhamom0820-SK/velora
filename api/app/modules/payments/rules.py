"""The payments module's rules, as data and pure functions (T-8.1).

- **Which store a man sees.** Each man is in price-test variant A or B by a
  hash of his id, stable for as long as he exists (`variant_of`). Since T-5.2
  retired `entry-25`, B has no active pack (D-250), so `SHOWN_AS` shows B the
  A packs until T-10.4 proposes a new test (D-480). An allowlist: a variant
  shows its own packs unless it is named here.
- **The first-purchase bonus**, a whole number of Velas, rounded down (D-231).
- **GST** (D-450, D-482): 0 while unregistered, and registered isn't built.
- **Turnover** (D-483): the Indian financial year, 1 April to 31 March in IST,
  and the levels its daily line is logged at.
- **A broken payment's claim** (T-8.3, D-580): its kinds, its statuses, and
  which of the gateway's payments on an order may be granted and which
  refunded.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Final
from uuid import UUID

from app.core.clock import IST
from app.core.providers.payments import ProviderPayment

# --- The store ----------------------------------------------------------------

VARIANTS: Final = ("A", "B")
# The hash's salt, so a later test (T-10.4) can split men afresh by changing it.
VARIANT_SALT: Final = b"price-test:"
# Variant -> the variant whose packs it is shown. B is shown A's until T-10.4
# (D-480): `entry-25` is retired (D-250), and no man is ever shown no packs.
SHOWN_AS: Final = MappingProxyType({"B": "A"})


def variant_of(user_id: UUID) -> str:
    """The man's price-test variant: the same answer for the same id, always,
    and about half of men in each."""
    digest = hashlib.sha256(VARIANT_SALT + user_id.bytes).digest()
    return VARIANTS[digest[0] % len(VARIANTS)]


def store_variant(user_id: UUID) -> str:
    """The variant whose active packs this man's store shows."""
    variant = variant_of(user_id)
    return SHOWN_AS.get(variant, variant)


def first_purchase_bonus(credits: int, bonus_first_pct: int, *, first: bool) -> int:
    """Bonus Velas on a man's first purchase, rounded down: 6, 20, 50 and 90 on
    D-099's packs (D-231); 0 on any later one."""
    return credits * bonus_first_pct // 100 if first else 0


# --- GST ------------------------------------------------------------------------


class GstNotBuilt(Exception):
    """Asked for a registered split, which is P-350's task to build. Settings
    refuses `GST_REGISTERED=true` first; this is the second lock."""


def gst_paise(amount_paise: int, *, registered: bool) -> int:
    """The government's part of an inclusive `amount_paise`: 0 unregistered
    (D-450). Registered, the split and its rounding are P-350's."""
    if registered:
        raise GstNotBuilt("the GST split is P-350's task; nothing computes it yet")
    return 0


# --- The order's key ------------------------------------------------------------

# What a client's `Idempotency-Key` may be: a UUID fits, and so does any
# 8-to-64-character token of letters, digits, `-` and `_`.
IDEMPOTENCY_KEY_PATTERN: Final = r"^[A-Za-z0-9_-]{8,64}$"


# --- Turnover -------------------------------------------------------------------

# ₹15 lakh, the alert, and ₹20 lakh, the threshold the law sets for services in
# a financial year (D-450, P-350). Paise (D-029).
TURNOVER_ALERT_PAISE: Final = 15_00_000 * 100
GST_THRESHOLD_PAISE: Final = 20_00_000 * 100


@dataclass(frozen=True)
class FinancialYear:
    """1 April to 31 March, in IST: `starts_at` inclusive, `ends_at` not."""

    first_year: int

    @property
    def label(self) -> str:
        return f"{self.first_year}-{(self.first_year + 1) % 100:02d}"

    @property
    def starts_at(self) -> datetime:
        return datetime(self.first_year, 4, 1, tzinfo=IST)

    @property
    def ends_at(self) -> datetime:
        return datetime(self.first_year + 1, 4, 1, tzinfo=IST)


def financial_year_of(instant: datetime) -> FinancialYear:
    """The financial year `instant` falls in, by India's calendar: 18:30 UTC on
    31 March is already the next one."""
    local = instant.astimezone(IST)
    return FinancialYear(local.year if local.month >= 4 else local.year - 1)


class TurnoverLevel(StrEnum):
    """The level the daily turnover line is logged at (D-483)."""

    INFO = "info"
    WARNING = "warning"  # from ₹15 lakh: the founder prepares to register
    ERROR = "error"  # from ₹20 lakh: register within 30 days (P-350)


def turnover_level(turnover_paise: int) -> TurnoverLevel:
    if turnover_paise >= GST_THRESHOLD_PAISE:
        return TurnoverLevel.ERROR
    if turnover_paise >= TURNOVER_ALERT_PAISE:
        return TurnoverLevel.WARNING
    return TurnoverLevel.INFO


# --- A broken payment's claim (T-8.3, D-580) ---------------------------------------


class ClaimReason(StrEnum):
    """What a man says broke. Never a change of mind: purchases are final
    (D-050, D-230)."""

    MISSING_VELAS = "missing_velas"  # the money went through, no Velas came
    DUPLICATE_CHARGE = "duplicate_charge"  # charged twice for one purchase


class ClaimStatus(StrEnum):
    OPEN = "open"
    GRANTED = "granted"  # the missing Velas, through the webhook's own capture
    REFUNDED = "refunded"  # a charge no Velas were granted for, returned
    REJECTED = "rejected"  # nothing broken; the admin's note says why


class ClaimAction(StrEnum):
    GRANT = "grant"
    REFUND = "refund"
    REJECT = "reject"


CURRENCY: Final = "INR"


def _untouched_capture(payment: ProviderPayment) -> bool:
    return payment.status == "captured" and payment.amount_refunded_paise == 0


def _for_the_order(payment: ProviderPayment, amount_paise: int) -> bool:
    return payment.amount_paise == amount_paise and payment.currency == CURRENCY


def grantable(
    held: list[ProviderPayment], *, anchor: str | None, amount_paise: int
) -> ProviderPayment | None:
    """The gateway's payment a grant credits: only while the row has credited
    none (no anchor), the first captured and untouched payment for exactly the
    row's amount, in rupees. Anything else is no purchase of this order's."""
    if anchor is not None:
        return None
    return next(
        (
            payment
            for payment in held
            if _untouched_capture(payment) and _for_the_order(payment, amount_paise)
        ),
        None,
    )


def refundable(
    held: list[ProviderPayment], *, anchor: str | None, amount_paise: int
) -> ProviderPayment | None:
    """The gateway's payment a refund returns: captured, untouched, and one no
    Velas can ever stand against (D-076 rule 3). Never the credited one, and,
    while none is credited, never one a grant could credit: its fix is the
    grant (D-050). So a second payment on a credited order, or one whose
    amount or currency isn't the order's."""
    return next(
        (
            payment
            for payment in held
            if _untouched_capture(payment)
            and payment.id != anchor
            and not (anchor is None and _for_the_order(payment, amount_paise))
        ),
        None,
    )
