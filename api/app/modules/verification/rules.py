"""What a face match means for a verification (T-4.5): the threshold, the
reasons, the attempts. No I/O: `service` applies these.

**The threshold is not ours** (D-260, Locked). 0.363 is the cosine similarity
OpenCV's face recognition tutorial publishes for SFace on LFW, a set of
celebrities' photos, beside four others for harder sets (CALFW 0.340, CPLFW
0.275, AgeDB-30 0.277, CFP-FP 0.212); it doesn't say how they were chosen. The
model's authors trained it, and these are their numbers on their data. Nobody
has measured how often it accepts the wrong person on selfies against Indian
profile photos, and no measurement set exists: the founder's words, 4 October
2026, "test kiye bina aage badho". So nothing we publish may say a person is
verified or is who they say (D-262), and every decision is looked at by a
person (D-264) until P-160 measures it.

**What it does and doesn't stop.** It catches a careless impostor: a selfie of
someone other than the person in the profile's photos. It does not stop a man who has a
woman's photos and one real selfie of her: that selfie matches her photos
closely, far from the threshold. Only liveness (T-4.11) or a person looking at
the selfie stops that, and until one exists, the person isn't optional.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final, Literal

from app.core.providers.facematch import FaceMatch

# D-260: SFace's published cosine threshold on LFW. At or above it, the selfie's
# face counts as matching a photo's.
MATCH_THRESHOLD: Final = 0.363

# What the `challenge` column holds since T-4.5: no pose is asked (the pose
# challenge is rejected; liveness is T-4.11's). D-263, so no migration.
NO_CHALLENGE: Final = "none"

# Five submitted selfies a day, a rolling 24 hours (T-4.5).
ATTEMPTS: Final = 5
ATTEMPT_WINDOW: Final = timedelta(hours=24)

# D-264: the near side of the threshold, listed first for the founder's review.
# A guess, not a measurement; `--all` lists every decision whatever its number.
REVIEW_FROM: Final = 0.25
REVIEW_BELOW: Final = 0.50

Reason = Literal[
    "no_face",
    "many_faces",
    "no_match",
    "no_photos",
    "unreadable",
    "unavailable",
]
NO_FACE: Final[Reason] = "no_face"  # no face found in the selfie
MANY_FACES: Final[Reason] = "many_faces"  # more than one
NO_MATCH: Final[Reason] = "no_match"  # below the threshold against every photo
NO_PHOTOS: Final[Reason] = "no_photos"  # no approved public photo with a face
UNREADABLE: Final[Reason] = "unreadable"  # not an image the pipeline can read
UNAVAILABLE: Final[Reason] = "unavailable"  # storage or the worker failed, finally
OTHER: Final = "other"

# The reasons an owner hears by name (D-263): every one of the above, each
# something they can act on. Anything else, a reason added later included,
# reaches them as `other` until someone lists it.
OWNER_REASONS: Final = frozenset(
    {NO_FACE, MANY_FACES, NO_MATCH, NO_PHOTOS, UNREADABLE, UNAVAILABLE}
)


def owner_reason(reason: str | None) -> str | None:
    if reason is None or reason in OWNER_REASONS:
        return reason
    return OTHER


def decide(match: FaceMatch) -> Reason | None:
    """None to approve, else why not: exactly one face in the selfie, and its
    best similarity with any approved photo at or above the threshold."""
    if match.faces_in_selfie == 0:
        return NO_FACE
    if match.faces_in_selfie > 1:
        return MANY_FACES
    best = match.best
    if best is None:
        return NO_PHOTOS
    if best >= MATCH_THRESHOLD:
        return None
    return NO_MATCH


# --- The founder's review (D-264) -----------------------------------------------------

Verdict = Literal["same", "different"]
VERDICTS: Final = frozenset({"same", "different"})


def near_the_threshold(best: float | None) -> bool:
    return best is not None and REVIEW_FROM <= best < REVIEW_BELOW


def mixed(approved: bool, similarities: list[float | None]) -> bool:
    """Approved on its best photo, while another photo with a face scored below
    the threshold: a profile whose photos may not all be one person (P-162)."""
    return approved and any(s is not None and s < MATCH_THRESHOLD for s in similarities)
