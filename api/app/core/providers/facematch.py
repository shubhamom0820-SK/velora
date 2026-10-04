"""Face match: is the selfie the person in the approved photos? (T-4.5)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FaceMatch:
    similarity: (
        float  # the selfie's best match among the references; T-4.5 sets its scale
    )
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


class SFaceFaceMatch:
    """On our own worker: YuNet finds the face, SFace compares it (D-088). No
    third party sees a selfie for this (D-087). Not built yet."""

    async def compare(self, selfie: bytes, references: Sequence[bytes]) -> FaceMatch:
        raise NotImplementedError("SFace face match arrives with T-4.5.")
