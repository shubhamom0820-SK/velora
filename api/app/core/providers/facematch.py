"""Face match: is the selfie the person in the approved photos? (T-4.5)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FaceMatch:
    similarity: float  # 0–100: the selfie's best match among the references
    faces_in_selfie: int


class FaceMatchProvider(Protocol):
    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        """Compare a selfie with the user's approved public photos."""
        ...


class FakeFaceMatch:
    """A clear match (99, one face), unless a test sets `next` for the next compare."""

    MATCH = FaceMatch(similarity=99.0, faces_in_selfie=1)

    def __init__(self) -> None:
        self.next: FaceMatch | None = None
        self.compared: list[tuple[bytes, tuple[bytes, ...]]] = []

    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        self.compared.append((selfie, tuple(references)))
        result, self.next = self.next or self.MATCH, None
        return result


class RekognitionFaceMatch:
    """AWS Rekognition via aioboto3. Not built yet."""

    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        raise NotImplementedError("Rekognition face match arrives with T-4.5.")
