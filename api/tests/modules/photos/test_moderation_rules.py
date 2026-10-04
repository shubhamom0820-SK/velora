"""D-101: what Sightengine's scores mean, each threshold at its edge (the
founder, 4 October 2026). A possible minor at 0.35 was chosen for an asymmetry,
not from data, and is revisited from real scores (T-9.5)."""

from __future__ import annotations

import pytest

from app.core.enums import PhotoKind
from app.core.providers.moderation import Scores
from app.modules.photos.moderation import verdict

QUIET = {
    "sexual_activity": 0.01,
    "sexual_display": 0.01,
    "erotica": 0.01,
    "very_suggestive": 0.01,
}


def _scores(
    *,
    minors: tuple[float, ...] = (0.01,),
    explicit: float = 0.01,
    text: float = 0.01,
    artificial_faces: int = 0,
) -> Scores:
    return Scores(
        nudity={**QUIET, "erotica": explicit},
        minors=minors,
        artificial_faces=artificial_faces,
        text_artificial=text,
    )


@pytest.mark.parametrize(
    ("minor", "expected"),
    [(0.35, "minor_suspected"), (0.3499, None), (0.5, "minor_suspected")],
)
def test_a_possible_minor_from_0_35(minor: float, expected: str | None) -> None:
    """The cautious side of the coin flip: faces near 18 score near 0.5."""
    assert verdict(_scores(minors=(0.02, minor)), PhotoKind.PUBLIC) == expected


@pytest.mark.parametrize(("explicit", "expected"), [(0.5, "nudity"), (0.4999, None)])
def test_nudity_from_0_5(explicit: float, expected: str | None) -> None:
    assert verdict(_scores(explicit=explicit), PhotoKind.PRIVATE) == expected


def test_the_merely_suggestive_classes_decide_nothing() -> None:
    """Swimwear and the merely suggestive pass: the reader doesn't even carry
    them (`NUDITY_CLASSES`)."""
    assert set(_scores().nudity) == set(QUIET)


@pytest.mark.parametrize(
    ("kind", "expected"), [(PhotoKind.PUBLIC, "no_face"), (PhotoKind.PRIVATE, None)]
)
def test_no_face_only_for_public_photos(kind: PhotoKind, expected: str | None) -> None:
    """An artificial face is nobody's: no real face is no face."""
    assert verdict(_scores(minors=(), artificial_faces=1), kind) == expected


@pytest.mark.parametrize(("text", "expected"), [(0.8, "text_overlay"), (0.7999, None)])
def test_overlaid_text_from_0_8(text: float, expected: str | None) -> None:
    assert verdict(_scores(text=text), PhotoKind.PUBLIC) == expected
