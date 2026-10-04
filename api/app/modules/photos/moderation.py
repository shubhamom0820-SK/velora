"""What Sightengine's scores mean for a photo (T-4.4).

The thresholds are D-101's, decided by the founder on 4 October 2026; each
says what it costs both ways. Checked in this order, the first that holds
deciding:

1. **A possible minor** (D-093): any real face scored 0.35 or more as a
   minor's. **0.35 was chosen for an asymmetry, not from data:** nobody has
   seen how this model scores real photos. A false positive costs a
   young-looking woman a polite "try a different photo"; a false negative puts
   a minor's photo on a dating app. With costs that far apart, the threshold
   sits on the cautious side of Sightengine's coin flip (faces near 18 score
   close to 0.5). Revisited from real scores (T-9.5). Checked first, so a photo
   that scores a minor and nudity is handled as D-093 says (the image deleted),
   never kept as an ordinary rejection.
2. **Nudity:** sexual activity, sexual display, erotica or "very suggestive" at
   0.5 or more. Swimwear, a bare chest and other merely suggestive photos pass:
   ordinary on dating profiles, and turning them away would reject many real
   ones.
3. **No face, public photos only:** no real face at all (drawings, statues and
   masks don't count). Others see a public photo as the person; a private one
   is shown only to people its owner chose (T-8.4).
4. **Text drawn on:** embedded text at 0.8 or more. Phone numbers and handles
   overlaid on a photo would get round the chat's contact masking (T-7.3);
   text in the scene, a sign or a T-shirt, is natural text and passes, and
   0.8 rather than 0.5 keeps a faint caption from rejecting a real photo.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from app.core.enums import PhotoKind
from app.core.providers.moderation import MODELS, Scores

Reason = Literal["nudity", "minor_suspected", "no_face", "text_overlay"]
NUDITY: Final = "nudity"
MINOR_SUSPECTED: Final = "minor_suspected"
NO_FACE: Final = "no_face"
TEXT_OVERLAY: Final = "text_overlay"
# Not a score: the worker's own, for an upload Pillow can't read as the image
# its bytes said it was, or one past the pixel limit (D-092).
OTHER: Final = "other"

MINOR_AT: Final = 0.35  # an asymmetry, not data: see above (D-101)
EXPLICIT: Final = ("sexual_activity", "sexual_display", "erotica", "very_suggestive")
NUDITY_AT: Final = 0.5
TEXT_AT: Final = 0.8


def verdict(scores: Scores, kind: PhotoKind) -> Reason | None:
    """None to approve, or the reason to reject."""
    if any(score >= MINOR_AT for score in scores.minors):
        return "minor_suspected"
    if max(scores.nudity[name] for name in EXPLICIT) >= NUDITY_AT:
        return "nudity"
    if kind is PhotoKind.PUBLIC and not scores.minors:
        return "no_face"
    if scores.text_artificial >= TEXT_AT:
        return "text_overlay"
    return None


def summary(scores: Scores) -> dict[str, Any]:
    """What `photos.moderation` keeps: every score the decision read, never the
    image or anything about the request. The minor score is kept for every
    photo, below the threshold too: D-101's 0.35 is revisited from these (T-9.5)."""
    return {
        "provider": "sightengine",
        "models": list(MODELS),
        "minor": max(scores.minors, default=None),
        "explicit": max(scores.nudity[name] for name in EXPLICIT),
        "faces": len(scores.minors),
        "artificial_faces": scores.artificial_faces,
        "text_artificial": scores.text_artificial,
    }
