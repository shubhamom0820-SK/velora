"""The real face match (D-088, T-4.5): YuNet and SFace through OpenCV, on the
worker, and the models it reads.

On NASA's public-domain portraits in `tests/fixtures/faces/`. **They prove
the mechanism, never accuracy:** that SFace tells these two people apart says
nothing about how often it confuses two others. No measurement of that exists
(D-260); until P-160 makes one, a person looks at every decision (D-264).

Needs the models (`make models`); skipped locally without them, failed in CI.
"""

from __future__ import annotations

import asyncio
import io
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.core import facemodels
from app.core.images import reencode
from app.core.providers.facematch import (
    FaceMatchUnavailable,
    SFaceFaceMatch,
)
from app.modules.verification import rules
from tests.infra import API_DIR, require_models

FACES = Path(__file__).resolve().parents[1] / "fixtures" / "faces"


def _face(name: str) -> bytes:
    return (FACES / f"{name}.jpg").read_bytes()


def _no_face() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (600, 800), "teal").save(out, "JPEG")
    return reencode(out.getvalue(), "image/jpeg").data


@pytest.fixture(scope="module")
def sface() -> SFaceFaceMatch:
    require_models()
    provider = SFaceFaceMatch()
    provider.load()
    return provider


async def test_the_same_person_four_years_apart_matches(sface: SFaceFaceMatch) -> None:
    match = await sface.compare(_face("chari_2021"), [_face("chari_2017")])

    assert match.faces_in_selfie == 1
    assert match.best is not None and match.best >= rules.MATCH_THRESHOLD
    assert match.model == "yunet-2023mar+sface-2021dec"


async def test_a_different_person_doesnt(sface: SFaceFaceMatch) -> None:
    """Two people of Indian origin, one man and one woman: far apart here, and
    that is all it shows."""
    match = await sface.compare(_face("williams_2004"), [_face("chari_2017")])

    assert match.best is not None and match.best < rules.MATCH_THRESHOLD


async def test_each_photo_is_compared_in_order_and_the_best_counts(
    sface: SFaceFaceMatch,
) -> None:
    match = await sface.compare(
        _face("chari_2021"),
        [_face("williams_2004"), _no_face(), _face("chari_2017")],
    )

    low, nothing, high = match.similarities
    assert nothing is None
    assert low is not None and high is not None
    assert low < rules.MATCH_THRESHOLD <= high == match.best


async def test_a_group_photo_is_compared_by_its_largest_face(
    sface: SFaceFaceMatch,
) -> None:
    """Chari is in the group photo, but not its largest face: the photo's
    subject is taken to be the largest, so it doesn't count for him here."""
    match = await sface.compare(_face("chari_2017"), [_face("three_people")])

    [similarity] = match.similarities
    assert similarity is not None and similarity < rules.MATCH_THRESHOLD


@pytest.mark.parametrize(("name", "faces"), [("three_people", 3), (None, 0)])
async def test_a_selfie_without_exactly_one_face_compares_nothing(
    sface: SFaceFaceMatch, name: str | None, faces: int
) -> None:
    selfie = _no_face() if name is None else _face(name)

    match = await sface.compare(selfie, [_face("chari_2017")])

    assert (match.faces_in_selfie, match.similarities) == (faces, (None,))
    assert rules.decide(match) == ("no_face" if faces == 0 else "many_faces")


async def test_opencv_never_parses_an_image_file(
    sface: SFaceFaceMatch, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pillow decodes every image (D-092, pinned and bounded); OpenCV is handed
    pixels only, so its image decoders never see a byte of an upload."""
    import cv2

    def refused(*args: object, **kwargs: object) -> None:
        raise AssertionError("OpenCV was asked to decode an image")

    for decoder in ("imdecode", "imread", "imreadmulti"):
        monkeypatch.setattr(cv2, decoder, refused)

    match = await sface.compare(_face("chari_2021"), [_face("chari_2017")])

    assert match.best is not None


def test_the_api_never_loads_opencv() -> None:
    """The API builds every provider, this one included, and must not carry
    OpenCV or the models: they are the worker's (D-088's 1 GB machine)."""
    probe = (
        "import sys\n"
        "import app.main\n"
        "from app.core.providers import build_providers\n"
        "from tests.conftest import make_test_settings\n"
        "s = make_test_settings().model_copy(update={'FACEMATCH_PROVIDER': 'sface'})\n"
        "build_providers(s)\n"
        "print('cv2' in sys.modules, 'numpy' in sys.modules)\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )

    assert done.stdout.strip().splitlines()[-1] == "False False"


# --- The models: exactly D-088's -----------------------------------------------------


def test_the_models_are_d088s() -> None:
    assert (facemodels.DETECTOR.size, facemodels.DETECTOR.sha256) == (
        232_589,
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    )
    assert (facemodels.RECOGNIZER.size, facemodels.RECOGNIZER.sha256) == (
        38_696_353,
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    )
    for model in facemodels.MODELS:
        assert model.url.startswith(
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
            "47534e27c9851bb1128ccc0102f1145e27f23f98/"
        )


def test_load_refuses_a_model_that_isnt_d088s(tmp_path: Path) -> None:
    require_models()
    for model in facemodels.MODELS:
        (tmp_path / model.name).write_bytes(
            (facemodels.MODEL_DIR / model.name).read_bytes()
        )
    altered = bytearray((tmp_path / facemodels.DETECTOR.name).read_bytes())
    altered[-1] ^= 0x01
    (tmp_path / facemodels.DETECTOR.name).write_bytes(bytes(altered))

    with pytest.raises(FaceMatchUnavailable, match="yunet_2023mar.onnx is not D-088"):
        SFaceFaceMatch(tmp_path).load()
    with pytest.raises(FaceMatchUnavailable, match="missing from"):
        SFaceFaceMatch(tmp_path / "nowhere").load()


def _serving(body_of: dict[str, bytes], calls: list[str]) -> httpx.MockTransport:
    def answer(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=body_of[str(request.url)])

    return httpx.MockTransport(answer)


def test_fetch_keeps_only_what_matches_and_fetches_nothing_twice(
    tmp_path: Path,
) -> None:
    require_models()
    real = {
        m.url: (facemodels.MODEL_DIR / m.name).read_bytes() for m in facemodels.MODELS
    }
    calls: list[str] = []

    asyncio.run(facemodels.fetch(tmp_path, transport=_serving(real, calls)))
    asyncio.run(facemodels.fetch(tmp_path, transport=_serving(real, calls)))

    assert facemodels.problems(tmp_path) == []
    assert calls == [m.url for m in facemodels.MODELS]


def test_fetch_refuses_an_altered_download_and_leaves_nothing(tmp_path: Path) -> None:
    altered = {m.url: b"not the model" for m in facemodels.MODELS}

    with pytest.raises(ValueError, match="face_detection_yunet_2023mar.onnx"):
        asyncio.run(facemodels.fetch(tmp_path, transport=_serving(altered, [])))

    assert list(tmp_path.iterdir()) == []
