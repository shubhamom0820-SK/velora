"""Face match: how closely the face in a selfie resembles the faces in the
person's approved photos (T-4.5).

Numbers only: the provider counts and compares, and
`verification.rules.decide` decides what they mean. It never says that two
photos show the same person, only how similar the faces are (D-262).

`SFaceFaceMatch` runs on our own worker: YuNet finds the faces, SFace compares
them, through OpenCV (D-088), and no third party sees a selfie for it (D-087).
Two rules keep it narrow:
- **OpenCV never parses an image file.** Every image here is a JPEG our own
  pipeline wrote (D-092's re-encode), and Pillow, pinned and bounded, decodes
  it; OpenCV is handed pixels only. Its only file input is the two models,
  each checked against D-088's SHA-256 before it is read (`core/facemodels`).
- **The API never loads it.** `build_providers` makes one in every process,
  so constructing it is free: `cv2` is imported, and the models read, only by
  `load()`, which the worker calls at startup.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol

from PIL import Image

from app.core import facemodels

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class FaceMatch:
    """What a comparison found: how many faces the selfie holds, and, when it
    holds exactly one, its cosine similarity with each reference photo's face,
    in the order given (`None` for a photo with no face found)."""

    model: str
    faces_in_selfie: int
    similarities: tuple[float | None, ...]

    @property
    def best(self) -> float | None:
        found = [s for s in self.similarities if s is not None]
        return max(found) if found else None


class FaceMatchUnavailable(Exception):
    """The models aren't there, or aren't D-088's: the worker can't compare."""


class FaceMatchProvider(Protocol):
    @property
    def model(self) -> str: ...

    def load(self) -> None:
        """Get ready to compare; raises `FaceMatchUnavailable` if it can't."""
        ...

    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        """Compare a selfie with the user's approved public photos. Every image
        is a JPEG our own re-encode wrote."""
        ...


class FakeFaceMatch:
    """One face, and `SIMILARITY` with every reference, unless a test sets
    `next` for the next compare: a `FaceMatch`, or `"fail"` to raise."""

    SIMILARITY: Final = 0.9

    def __init__(self) -> None:
        self.next: FaceMatch | str | None = None
        self.compared: list[tuple[bytes, tuple[bytes, ...]]] = []
        self.loaded = False

    @property
    def model(self) -> str:
        return "fake"

    def load(self) -> None:
        self.loaded = True

    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        self.compared.append((selfie, tuple(references)))
        result, self.next = self.next, None
        if result == "fail":
            raise RuntimeError("the fake face match failed, as a test asked")
        if isinstance(result, FaceMatch):
            return result
        return FaceMatch(
            model=self.model,
            faces_in_selfie=1,
            similarities=tuple(self.SIMILARITY for _ in references),
        )


# YuNet's settings, as OpenCV Zoo's own demo runs it: a face is one it scores
# 0.9 or more; overlapping boxes above 0.3 are one face.
DETECTION_SCORE: Final = 0.9
_NMS: Final = 0.3
_TOP_K: Final = 5000


class SFaceFaceMatch:
    """YuNet and SFace through OpenCV, on the worker (D-088).

    The selfie must hold exactly one face; each reference photo is compared by
    its largest face (the photo's subject, ahead of anyone behind them), and a
    reference with none found counts as `None`."""

    def __init__(self, model_dir: Path | None = None) -> None:
        self._model_dir = model_dir or facemodels.MODEL_DIR
        self._detector: Any = None
        self._recognizer: Any = None

    @property
    def model(self) -> str:
        return "yunet-2023mar+sface-2021dec"

    def load(self) -> None:
        if self._recognizer is not None:
            return
        wrong = facemodels.problems(self._model_dir)
        if wrong:
            raise FaceMatchUnavailable(
                "; ".join(wrong) + ". Fetch them with `make models` (D-088)."
            )
        import cv2

        # OpenCV 5's graph engine warns about targets once per model it loads.
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
        self._detector = cv2.FaceDetectorYN.create(
            str(self._model_dir / facemodels.DETECTOR.name),
            "",
            (320, 320),
            DETECTION_SCORE,
            _NMS,
            _TOP_K,
        )
        self._recognizer = cv2.FaceRecognizerSF.create(
            str(self._model_dir / facemodels.RECOGNIZER.name), ""
        )

    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        self.load()
        image = _pixels(selfie)
        faces = self._faces(image)
        if len(faces) != 1:
            return FaceMatch(self.model, len(faces), tuple(None for _ in references))
        mine = self._feature(image, faces[0])
        return FaceMatch(
            self.model,
            1,
            tuple(self._similarity(mine, reference) for reference in references),
        )

    def _faces(self, image: np.ndarray) -> list[np.ndarray]:
        height, width = image.shape[:2]
        self._detector.setInputSize((width, height))
        _, found = self._detector.detect(image)
        return [] if found is None else list(found)

    def _feature(self, image: np.ndarray, face: np.ndarray) -> np.ndarray:
        feature: np.ndarray = self._recognizer.feature(
            self._recognizer.alignCrop(image, face)
        )
        return feature

    def _similarity(self, mine: np.ndarray, reference: bytes) -> float | None:
        import cv2

        image = _pixels(reference)
        faces = self._faces(image)
        if not faces:
            return None
        largest = max(faces, key=lambda face: float(face[2] * face[3]))
        theirs = self._feature(image, largest)
        return float(
            self._recognizer.match(mine, theirs, cv2.FaceRecognizerSF_FR_COSINE)
        )


def _pixels(jpeg: bytes) -> np.ndarray:
    """A JPEG our re-encode wrote, decoded by Pillow (D-092: its pixel limit
    holds here too) and handed to OpenCV as BGR pixels."""
    import numpy as np

    with Image.open(io.BytesIO(jpeg), formats=["JPEG"]) as decoded:
        rgb = decoded.convert("RGB")
    return np.ascontiguousarray(np.asarray(rgb)[:, :, ::-1])
