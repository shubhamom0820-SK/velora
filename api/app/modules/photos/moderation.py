"""What Sightengine's scores mean for a photo (T-4.4).

The thresholds are Claude's proposal, made in T-4.4 and the founder's to change
(D-101, Open); each says what it costs both ways. Checked in this order, the
first that holds deciding:

1. **A possible minor** (D-093): any real face scored 0.5 or more as a minor's.
   Sightengine's documentation says faces near 18 score close to 0.5, so this
   catches young-looking adults as well. D-093 accepts that: the photo is
   rejected without an accusation, and a young adult tries another photo; a
   minor's photo left on a dating app is the harm the rule exists for. Checked
   first, so a photo that scores a minor and nudity is handled as D-093 says
   (the image deleted), never kept as an ordinary rejection.
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

MINOR_AT: Final = 0.5
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
    """What `photos.moderation` keeps: the scores the decision read, never the
    image or anything about the request."""
    return {
        "provider": "sightengine",
        "models": list(MODELS),
        "explicit": max(scores.nudity[name] for name in EXPLICIT),
        "faces": len(scores.minors),
        "artificial_faces": scores.artificial_faces,
        "text_artificial": scores.text_artificial,
    }
