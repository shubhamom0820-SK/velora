"""What a message may say (D-030, D-552): refused, masked, or as written. No I/O.

Two checks, in this order, on every message's text:

1. **Refused** (`MESSAGE_REJECTED`, with the rule's name): abuse, or asking for
   money. `/terms` promises both: "We refuse messages that are abusive or that
   ask for money." Checked on every message, ever, never only the first 20.
2. **Masked**, in a Thread's first `mask_first_n_messages` (seeded 20): phone
   numbers, email addresses and UPI IDs, and social handles. Each match becomes
   dots, at most twelve. The original is kept in `body_raw` for moderation.

The lists are the prototype's (`docs/prototype`, "text safety filters"), with
three changes, each because the prototype's version refused or hid ordinary
sentences (the founder, 8 October 2026, D-552):
- "transfer" and "upi" refuse only inside a money phrase ("transfer money",
  "upi id"), never alone: "I'm transferring jobs" is a life, not a payment.
- a handle needs its app named and then a separator (`insta: x`, `snap @x`,
  `insta id x`): the prototype's `wa` followed by any three letters hid
  "watching" and "water".
- any `name@handle` is masked, which covers every UPI app's suffix rather than
  five of them.
Hindi and Hinglish words aren't here yet: P-450, the founder's list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

ABUSE: Final = "abuse"
SOLICITATION: Final = "solicitation"

# The prototype's ABUSE, as a prefix: "chutiya" is "chutiy".
_ABUSE = re.compile(
    r"\b(bitch|slut|whore|rape|randi|madarch|behench|chutiy)", re.IGNORECASE
)

_MONEY = r"(money|paise|paisa|rupees?|rs\.?|inr|₹)"
# An amount, if one is written before the money word: "500", "5,000".
_AMOUNT = r"(\d[\d,]*\s*)?"
_SOLICITATION = re.compile(
    r"\b(paytm|gpay|g\s?pay|phonepe|western\s+union)\b"
    rf"|\bsend\s+(me\s+)?(some\s+)?{_AMOUNT}{_MONEY}"
    rf"|\btransfer\s+(me\s+)?(the\s+|some\s+)?{_AMOUNT}{_MONEY}"
    rf"|\b{_MONEY}\s+transfer"
    r"|\bupi\s+(id|pe|par|kar\w*|me|number|no\b|details)",
    re.IGNORECASE,
)

_CONTACT = re.compile(
    # A phone number: a digit, at least eight digits, spaces or dashes, a digit.
    r"\+?\d[\d\s-]{8,}\d"
    # An email address or a UPI ID: anything@something.
    r"|[\w.+-]+@[\w-]+(\.[\w-]+)*"
    # A social handle: the app named, then a separator, then the handle.
    r"|\b(insta(gram)?|snap(chat)?|whats\s?app|wa|telegram|tg)\b"
    r"(\s*(:|@|-|\bid\b|\bis\b|\bhandle\b)\s*)+@?[\w.]+",
    re.IGNORECASE,
)

MASK: Final = "•"
MASK_MAX: Final = 12


def refusal(text: str) -> str | None:
    """The rule `text` breaks, or None: abuse first, then asking for money."""
    if _ABUSE.search(text):
        return ABUSE
    if _SOLICITATION.search(text):
        return SOLICITATION
    return None


@dataclass(frozen=True)
class Masked:
    body: str
    masked: bool


def mask(text: str) -> Masked:
    """`text` with every contact detail as dots; `masked` when any was."""
    body = _CONTACT.sub(lambda found: MASK * min(len(found[0]), MASK_MAX), text)
    return Masked(body=body, masked=body != text)
