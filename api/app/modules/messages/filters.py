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
Hindi and Hinglish, romanised and in Devanagari, are the founder's list (P-450,
D-981), which also records every word left out and why: each one an ordinary
word, a name, or a sentence people write. Devanagari has no `\b` in Python (its
vowel signs aren't word characters), so its edges are "no Devanagari beside
it"; and text and patterns are both NFC, so "ड़" matches typed either way.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

ABUSE: Final = "abuse"
SOLICITATION: Final = "solicitation"

# Devanagari's letters and signs: a word's edge is none of these beside it.
_DEV = "\u0900-\u097f"
_DEV_START = rf"(?<![{_DEV}])"
_DEV_END = rf"(?![{_DEV}])"


def _nfc(pattern: str) -> str:
    return unicodedata.normalize("NFC", pattern)


# The prototype's ABUSE, and P-450's: a prefix where a word has many endings
# ("chutiy" is "chutiya", "chutiye"), a whole word where a prefix would catch
# ordinary ones ("gaand", never "gaana").
_ABUSE_PREFIXES = (
    r"bitch|slut|whore|rape|randi|madarch|maderch|behench|bhench|bhen\s+chod"
    r"|chutiy|bhosd|bhosad|haramzad|haramkhor|chinal|chhinal|chinaal"
    r"|(behen|maa)\s+ke\s+(lode|laude|lawde|lund)"
)
_ABUSE_WORDS = (
    r"gandu|gaandu|gaand|lauda|lawda|lavda|laude|lodu|lund|harami|jhaantu|jhantu"
    r"|bsdk|bkl|mkc"
)
_ABUSE_DEV_PREFIXES = (
    "मादरचोद|बहनचोद|बहेनचोद|भेनचोद|भैनचोद|चूतिया|चुतिया|भोसड़|भोसड"
    "|हरामज़ाद|हरामजाद|हरामखोर|छिनाल|रंडी"
)
_ABUSE_DEV_WORDS = "गांडू|गाँडू|गाण्डू|गांड|गाँड|लौड़ा|लौडा|लंड|हरामी|झांटू|झाँटू"
_ABUSE = re.compile(
    _nfc(
        rf"\b({_ABUSE_PREFIXES})|\b({_ABUSE_WORDS})\b"
        rf"|{_DEV_START}({_ABUSE_DEV_PREFIXES})"
        rf"|{_DEV_START}({_ABUSE_DEV_WORDS}){_DEV_END}"
    ),
    re.IGNORECASE,
)

_MONEY = r"(money|paise|paisa|rupees?|rupaye|rs\.?|inr|₹)"
# An amount, if one is written before the money word: "500", "5,000".
_AMOUNT = r"(\d[\d,]*\s*)?"
# Asking, after the thing asked for. Never a bare "do": "paise do baar kat
# gaye" is money cut twice (the founder, P-450), and "udhaar do baar liya" is
# borrowing twice. A gift card's bare "do" is the founder's, kept.
_ASK = r"(bhejo|bhej\s*do|bhej\s*de|bhejna|de\s*do|dedo|do\s+na|chahiye|chahie)\b"
_DEV_MONEY = "(पैसे|पैसा|रुपये|रुपए|रुपया)"
_DEV_ASK = r"(भेजो|भेज\s*दो|भेज\s*दे|भेजना|दे\s*दो|दो\s+ना|चाहिए|चाहिये)"
_SOLICITATION = re.compile(
    _nfc(
        r"\b(paytm|gpay|g\s?pay|google\s*pay|amazon\s*pay|phonepe|mobikwik"
        r"|freecharge|bhim\s+upi|western\s+union)\b"
        rf"|\bsend\s+(me\s+)?(some\s+)?{_AMOUNT}{_MONEY}"
        rf"|\btransfer\s+(me\s+)?(the\s+|some\s+)?{_AMOUNT}{_MONEY}"
        rf"|\b{_MONEY}\s+transfer"
        r"|\bupi\s+(id|pe|par|kar\w*|me|number|no\b|details)"
        # Hinglish: the money, then the ask; an amount, then "send"; a
        # recharge, a loan, a QR code or a gift card asked for.
        rf"|(?<!\w){_MONEY}\s+{_ASK}"
        r"|(₹\s*|\b)\d[\d,]*\s*(rs\.?|rupaye|rupees?)?\s*bhej(o|\s*do|\s*de)\b"
        r"|\brecharge\s+(kar|kara|karwa)\s?(do|de|dena|doge|dogi)\b"
        r"|\budhaar\s+(de\s*do|dedo|do\s+na|chahiye|chahie)\b"
        r"|\bqr(\s*code)?\s+(bhejo|bhej\s*do|scan\s*karo|scan\s*kar\s*do)\b"
        r"|\bgift\s*card\s+(bhejo|bhej\s*do|do|de\s*do|dedo|chahiye|chahie)\b"
        # Devanagari.
        rf"|{_DEV_START}(पेटीएम|गूगल\s*पे|फोनपे|फ़ोनपे|यूपीआई){_DEV_END}"
        rf"|{_DEV_START}{_DEV_MONEY}\s*{_DEV_ASK}"
        rf"|(₹\s*|{_DEV_START})[\d०-९][\d०-९,]*\s*(रुपये|रुपए)?\s*भेज(ो|\s*दो|\s*दे)"
        rf"|{_DEV_START}रिचार्ज\s*(कर|करा|करवा)\s*(दो|दे|देना){_DEV_END}"
        rf"|{_DEV_START}उधार\s*(दे\s*दो|चाहिए|चाहिये)"
        rf"|{_DEV_START}(क्यूआर|क्यू\s*आर)(\s*कोड)?\s*(भेजो|भेज\s*दो|स्कैन\s*करो|स्कैन\s*कर\s*दो)"
        rf"|{_DEV_START}गिफ्ट\s*कार्ड\s*(भेजो|भेज\s*दो|दो|दे\s*दो|चाहिए|चाहिये){_DEV_END}"
    ),
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
    text = unicodedata.normalize("NFC", text)
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
