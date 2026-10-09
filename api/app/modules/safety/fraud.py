"""Fraud scoring v1 (D-031, T-9.2, D-900): the rules, no I/O.

Every signal is a `fraud_events` row a service writes as it sees something:
what was observed, never a verdict. The score is a rule, not a model (D-031:
no training data yet):

- **Decay:** an event counts its full weight when written, falling in a straight
  line to nothing at 7 days.
- **Caps:** each signal's decayed sum is capped, then the signals are added and
  the total held to 100. A report counts once per reporter, uncapped: the one
  signal that may freeze on its own, from five people in a week.
- **Bands** (D-031): below 30 normal, 30 to 59 monitor, 60 to 80 shadow, above
  80 freeze. D-031 left 60 and 80 to either side; both are shadow (D-900).
- **Three reports in 24 hours freeze, whatever the score** (D-031, D-901):
  from three numbers, each sharing a Thread with the person reported.

What the weights promise, and `test_fraud_rules.py` holds: no signal but reports
reaches shadow on its own, so nothing but people can take someone out of
everyone's deck or freeze them; a possible-minor score never leaves the normal
band on its own (D-093), and a chargeback never passes monitor (D-520).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from app.core.enums import FraudBand, UserStatus

# --- Signals -------------------------------------------------------------------------

REPORT_RECEIVED: Final = "report_received"
MESSAGE_REJECTED: Final = "message_rejected"
CONTACT_MASKED: Final = "contact_masked"
MANY_NEW_THREADS: Final = "many_new_threads"
IDENTICAL_FIRST_MESSAGE: Final = "identical_first_message"
MANY_SIGN_INS: Final = "many_sign_ins"
LOCATION_JUMP: Final = "location_jump"
POSSIBLE_MINOR_SCORE: Final = "possible_minor_photo_score"
CHARGEBACK_SHORTFALL: Final = "chargeback_shortfall"

# What each signal is worth as it is written: the row keeps it, so a weight
# changed later applies to new events only, and a record says what it counted.
WEIGHTS: Final[Mapping[str, int]] = {
    REPORT_RECEIVED: 20,
    CONTACT_MASKED: 2,
    MANY_NEW_THREADS: 25,
    IDENTICAL_FIRST_MESSAGE: 25,
    MANY_SIGN_INS: 15,
    LOCATION_JUMP: 15,
    POSSIBLE_MINOR_SCORE: 10,
    CHARGEBACK_SHORTFALL: 30,
}
# A refused message is worth what its rule says (D-552's two).
REJECTED_WEIGHTS: Final[Mapping[str, int]] = {"abuse": 10, "solicitation": 15}

# The most each signal may add, decayed. A signal with no cap here is a report's.
CAPS: Final[Mapping[str, int]] = {
    MESSAGE_REJECTED: 45,
    CONTACT_MASKED: 10,
    MANY_NEW_THREADS: 25,
    IDENTICAL_FIRST_MESSAGE: 25,
    MANY_SIGN_INS: 15,
    LOCATION_JUMP: 30,
    POSSIBLE_MINOR_SCORE: 20,
    CHARGEBACK_SHORTFALL: 30,
}
# A signal no rule here names (a later task's, before it says) adds this at most:
# under the monitor band, so an unknown name can't act on anyone.
UNKNOWN_CAP: Final = 25


def rejected_weight(rule: str) -> int:
    return REJECTED_WEIGHTS.get(rule, REJECTED_WEIGHTS["abuse"])


# --- Thresholds: when a service writes a signal ----------------------------------------

NEW_THREADS_MAX: Final = 30  # Threads they opened, more than this in 24 h
NEW_THREADS_WINDOW: Final = timedelta(hours=24)
IDENTICAL_MAX: Final = 10  # people sent the same first message, more than this
IDENTICAL_WINDOW: Final = timedelta(days=7)
SIGN_INS_MAX: Final = 3  # sign-ins (session families), more than this in 7 days (D-903)
SIGN_INS_WINDOW: Final = timedelta(days=7)
JUMP_KM: Final = 500  # moved more than this...
JUMP_WITHIN: Final = timedelta(hours=1)  # ...since the last location, this recent
# A threshold signal is written at most once in this long: crossing it again the
# same day says nothing new.
ONCE_PER: Final = timedelta(hours=24)


def jumped(km: float, since_last: timedelta) -> bool:
    return km > JUMP_KM and since_last <= JUMP_WITHIN


# --- The score -----------------------------------------------------------------------

DECAY: Final = timedelta(days=7)

MONITOR_FROM: Final = 30
SHADOW_FROM: Final = 60
FREEZE_ABOVE: Final = 80
MAX_SCORE: Final = 100

REPORTS_TO_FREEZE: Final = 3
REPORTS_WINDOW: Final = timedelta(hours=24)

# Who a freeze may reach (D-902, the founder's 7): an account that can sign in.
# A deleted one is left to its erasure, which a freeze would stop; a banned one
# is banned already.
FREEZABLE: Final = frozenset({UserStatus.ACTIVE, UserStatus.PAUSED})


@dataclass(frozen=True)
class Event:
    signal: str
    weight: int
    age: timedelta
    # Whose report this is, for a report: one counts per reporter.
    reporter: object | None = None


@dataclass(frozen=True)
class Scored:
    score: int
    # Each signal's share of the score, capped, rounded: `fraud_scores.signals`.
    signals: dict[str, int]


def decayed(weight: int, age: timedelta) -> float:
    """`weight` at `age`: whole when new (or dated ahead of the clock), nothing
    from 7 days on."""
    if age <= timedelta(0):
        return float(weight)
    left = 1 - age / DECAY
    return weight * left if left > 0 else 0.0


def score(events: Iterable[Event]) -> Scored:
    sums: dict[str, float] = defaultdict(float)
    reports: dict[object, float] = {}
    for event in events:
        value = decayed(event.weight, event.age)
        if event.signal == REPORT_RECEIVED:
            key = event.reporter if event.reporter is not None else id(event)
            reports[key] = max(reports.get(key, 0.0), value)
        else:
            sums[event.signal] += value
    shares = {
        signal: min(total, CAPS.get(signal, UNKNOWN_CAP))
        for signal, total in sums.items()
    }
    if reports:
        shares[REPORT_RECEIVED] = sum(reports.values())
    total = min(MAX_SCORE, round(sum(shares.values())))
    signals = {
        signal: round(share) for signal, share in sorted(shares.items()) if share > 0
    }
    return Scored(score=total, signals=signals)


def band(score: int, *, reporting_numbers: int = 0) -> FraudBand:
    """D-031's bands, and its three reports in 24 hours over any score."""
    if reporting_numbers >= REPORTS_TO_FREEZE or score > FREEZE_ABOVE:
        return FraudBand.FREEZE
    if score >= SHADOW_FROM:
        return FraudBand.SHADOW
    if score >= MONITOR_FROM:
        return FraudBand.MONITOR
    return FraudBand.NORMAL


# Band changes the audit log records: anything into or out of these, both of them
# automatic actions on a person.
ACTED: Final = frozenset({FraudBand.SHADOW, FraudBand.FREEZE})
