"""Photo moderation (T-4.4): Sightengine's plain image API, and its fake.

**The plain image moderation API only:** one `POST` to `check.json` with the
re-encoded JPEG in the request and the three models below, on Sightengine's
default retention, which deletes the image after processing. `/privacy`'s
"deleted there after the check" (D-048) rests on that. Never human review
(workflows), the Feedback API, the Upload API or lists: each keeps the file at
Sightengine, so turning one on is a decision that changes a published page,
not a tuning knob (T-4.4). A test holds every request to this one shape.

**The fake answers in Sightengine's shape (D-094).** It builds the JSON
`check.json` returns, from Sightengine's own documentation as corrected by a
real answer (`CHECKED_ANSWER`), and both go
through `parse_check`, so the code that reads a real answer is the code every
test runs. T-4.4's last step compared a real response's shape with the fake's
(`app/tools/sightengine_shape.py`); when Sightengine changes, that comparison,
not a green test, says so.

What the scores mean is the photos module's to decide (thresholds are business
rules, CLAUDE.md rule 8): this module only asks and reads.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol, cast

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

CHECK_URL: Final = "https://api.sightengine.com/1.0/check.json"
# Nudity, the minor probability of each real face (`face-age`, which replaced
# the deprecated `face-attributes`), and text drawn onto the image.
MODELS: Final = ("nudity-2.1", "face-age", "text")
TIMEOUT_S: Final = 30.0
# Which model gave which score, for the records that keep one (D-093).
MINOR_MODEL: Final = "sightengine face-age"


class ModerationFailed(Exception):
    """No answer we can read: Sightengine unreachable, slow, refusing, or
    answering in a shape this module doesn't know. Worth trying again. The
    message names a kind of failure, never a key or the image."""


@dataclass(frozen=True)
class Scores:
    """What the three models said about one image, each from 0 to 1."""

    # nudity-2.1's top-level classes, `none` included.
    nudity: Mapping[str, float]
    # One per real face: the probability it is a minor's. Empty: no real face.
    minors: tuple[float, ...]
    # Drawings, statues, masks: faces, but nobody's (face-age).
    artificial_faces: int
    text_artificial: float
    text_natural: float
    operations: int = 0


class ModerationProvider(Protocol):
    async def check(self, image: bytes) -> Scores:
        """Ask about a re-encoded JPEG. Raises `ModerationFailed`."""
        ...

    async def aclose(self) -> None:
        """Release connections. Safe to call more than once."""
        ...


# --- The response, as Sightengine documents it -----------------------------------
#
# Strict: a score that arrives as a string, a field renamed or moved, fails here,
# loudly, and the photo waits; it never reads as 0 and passes. Fields not read
# are still listed, so the fake can't drift from the checked shape either.


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow", frozen=True)


class _RequestInfo(_Strict):
    id: str
    timestamp: float
    operations: int


class _Nudity(_Strict):
    sexual_activity: float
    sexual_display: float
    erotica: float
    very_suggestive: float
    suggestive: float
    mildly_suggestive: float
    suggestive_classes: dict[str, Any]
    none: float
    context: dict[str, float]


class _Age(_Strict):
    minor: float


class _FaceAttributes(_Strict):
    age: _Age


class _Face(_Strict):
    x1: float
    y1: float
    x2: float
    y2: float
    attributes: _FaceAttributes


class _Box(_Strict):
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    prob: float


class _Text(_Strict):
    has_artificial: float
    has_natural: float
    # Absent when there is no text, not an empty list: see CHECKED_ANSWER.
    boxes: list[_Box] | None = None


class _Media(_Strict):
    id: str
    uri: str


class _Check(_Strict):
    status: Literal["success"]
    request: _RequestInfo
    nudity: _Nudity
    faces: list[_Face]
    artificial_faces: list[Any]
    text: _Text
    media: _Media


NUDITY_CLASSES: Final = (
    "sexual_activity",
    "sexual_display",
    "erotica",
    "very_suggestive",
    "suggestive",
    "mildly_suggestive",
    "none",
)


def parse_check(body: bytes | str) -> Scores:
    """A `check.json` answer, read; `ModerationFailed` for anything else."""
    try:
        check = _Check.model_validate_json(body)
    except ValidationError:
        raise ModerationFailed(_failure_kind(body)) from None
    return Scores(
        nudity={name: getattr(check.nudity, name) for name in NUDITY_CLASSES},
        minors=tuple(face.attributes.age.minor for face in check.faces),
        artificial_faces=len(check.artificial_faces),
        text_artificial=check.text.has_artificial,
        text_natural=check.text.has_natural,
        operations=check.request.operations,
    )


class _Failure(BaseModel):
    model_config = ConfigDict(extra="allow")

    class _Error(BaseModel):
        model_config = ConfigDict(extra="allow")
        type: str = "unknown"
        code: int | str = "unknown"

    status: Literal["failure"]
    error: _Error


def _failure_kind(body: bytes | str) -> str:
    """Sightengine's own error type and code, if it said one; else that the
    answer had a shape we don't know. Never the body: it echoes the request."""
    try:
        failure = _Failure.model_validate_json(body)
    except ValidationError:
        return "an answer in a shape this module doesn't know"
    return f"Sightengine refused: {failure.error.type} ({failure.error.code})"


# --- The real one -------------------------------------------------------------------


class SightengineModeration:
    """Sightengine over httpx: one `check.json` call per image.

    The client opens on first use, so the API, which builds every provider and
    never moderates, opens none. Its keys go in the form body, never the URL,
    which httpx logs.
    """

    def __init__(
        self,
        api_user: str,
        api_secret: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._form = {
            "models": ",".join(MODELS),
            "api_user": api_user,
            "api_secret": api_secret,
        }
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def check(self, image: bytes) -> Scores:
        return parse_check(await self.check_raw(image))

    async def check_raw(self, image: bytes) -> bytes:
        """The answer's body as sent, once it says success or failure:
        `parse_check` reads it, and T-4.4's shape check compares it."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=TIMEOUT_S, transport=self._transport
            )
        try:
            response = await self._client.post(
                CHECK_URL,
                data=self._form,
                files={"media": ("photo.jpg", image, "image/jpeg")},
            )
        except httpx.HTTPError as error:
            raise ModerationFailed(
                f"no answer from Sightengine ({type(error).__name__})"
            ) from None
        if response.status_code != 200:
            raise ModerationFailed(
                f"Sightengine answered {response.status_code}: "
                + _failure_kind(response.content)
            )
        return response.content

    async def aclose(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()


# --- The fake ------------------------------------------------------------------------

FakeOutcome = Literal[
    "approve", "nudity", "minor_suspected", "no_face", "text_overlay", "fail"
]
_REJECTIONS: Final = ("nudity", "minor_suspected", "no_face", "text_overlay")

# Sightengine's answer, field for field: nudity-2.1's from
# /docs/advanced-nudity-detection-model-2.1, face-age's from
# /docs/face-age-minor-detection, text's from /docs/text-detection-model (read
# 4 October 2026), merged into the one answer a call with all three models
# gives; then corrected where real answers differ from the documentation, as
# D-094's check found on 4 October 2026 (T-4.4 records it): with no text in the
# image, `text.boxes` is absent, not an empty list, and each box carries a
# `prob`, which the documentation doesn't show. The scores are an ordinary
# adult's photo with no text on it.
CHECKED_ANSWER: Final[Mapping[str, Any]] = {
    "status": "success",
    "request": {
        "id": "req_1SJJxJjUHnSVWreApx9fF",
        "timestamp": 1693574119.571633,
        "operations": 3,
    },
    "nudity": {
        "sexual_activity": 0.01,
        "sexual_display": 0.01,
        "erotica": 0.01,
        "very_suggestive": 0.01,
        "suggestive": 0.01,
        "mildly_suggestive": 0.01,
        "suggestive_classes": {
            "bikini": 0.01,
            "cleavage": 0.01,
            "cleavage_categories": {
                "very_revealing": 0.01,
                "revealing": 0.01,
                "none": 0.99,
            },
            "lingerie": 0.01,
            "male_chest": 0.01,
            "male_chest_categories": {
                "very_revealing": 0.01,
                "revealing": 0.01,
                "slightly_revealing": 0.01,
                "none": 0.99,
            },
            "male_underwear": 0.01,
            "miniskirt": 0.01,
            "other": 0.01,
            "minishort": 0.11,
            "nudity_art": 0.01,
            "schematic": 0.01,
            "sextoy": 0.01,
            "suggestive_focus": 0.01,
            "suggestive_pose": 0.01,
            "swimwear_male": 0.01,
            "swimwear_one_piece": 0.01,
            "visibly_undressed": 0.01,
        },
        "none": 0.99,
        "context": {
            "sea_lake_pool": 0.01,
            "outdoor_other": 0.99,
            "indoor_other": 0.01,
        },
    },
    "faces": [
        {
            "x1": 0.435,
            "y1": 0.2439,
            "x2": 0.5675,
            "y2": 0.4991,
            "attributes": {"age": {"minor": 0.01}},
        }
    ],
    "artificial_faces": [],
    "text": {"has_artificial": 0.01, "has_natural": 0.02},
    "media": {"id": "med_1SJJEFuLqeSedThQjhNoS", "uri": "photo.jpg"},
}


def fake_answer(outcome: FakeOutcome) -> dict[str, Any]:
    """The checked answer, its scores moved to give `outcome`: the
    documentation's own examples where it has them (a minor's face at 0.93,
    embedded text at 0.99932 with its box)."""
    answer = copy.deepcopy(dict(CHECKED_ANSWER))
    if outcome == "nudity":
        answer["nudity"].update(sexual_display=0.97, none=0.02)
    elif outcome == "minor_suspected":
        answer["faces"][0]["attributes"]["age"]["minor"] = 0.93
    elif outcome == "no_face":
        answer["faces"] = []
    elif outcome == "text_overlay":
        answer["text"] = {
            "has_artificial": 0.99932,
            "has_natural": 0.19986,
            "boxes": [
                {
                    "x1": 0.18466,
                    "y1": 0.01757,
                    "x2": 0.8555,
                    "y2": 0.244,
                    "label": "text-artificial",
                    "prob": 0.99,
                }
            ],
        }
    return answer


@dataclass
class FakeModeration:
    """Answers in Sightengine's shape; approves, unless a test sets `next`
    (06-TESTING). `next = "reject:nudity"` makes the next check score that
    reason; `next = "fail"` makes it fail as an unreachable Sightengine would.
    Either is one-shot: the check after it approves again."""

    next: str = "approve"
    checked: list[bytes] = field(default_factory=list)

    async def check(self, image: bytes) -> Scores:
        self.checked.append(image)
        outcome, self.next = self.next, "approve"
        if outcome == "fail":
            raise ModerationFailed("the fake was told to fail")
        if outcome != "approve":
            kind, _, reason = outcome.partition(":")
            if kind != "reject" or reason not in _REJECTIONS:
                raise ValueError(
                    "FakeModeration.next must be 'approve', 'fail' or "
                    f"'reject:<reason>' with a reason from {sorted(_REJECTIONS)}, "
                    f"not {outcome!r}. ('other' is the worker's own, for an image "
                    "it can't read; no score gives it.)"
                )
            outcome = reason
        return parse_check(json.dumps(fake_answer(cast(FakeOutcome, outcome))))

    async def aclose(self) -> None:
        return None
