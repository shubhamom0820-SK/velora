"""The two face models the worker runs (D-088, T-4.5): where they come from,
what they must be, and fetching them.

- **YuNet** finds faces: `face_detection_yunet_2023mar.onnx`, MIT.
- **SFace** compares them: `face_recognition_sface_2021dec.onnx`, Apache-2.0.

Both come from OpenCV Zoo at one pinned commit, and are fetched, never
committed: the image's build fetches them (`api/Dockerfile`), CI fetches them
for the tests, and `make models` fetches them locally into `api/models/`
(git-ignored). Every copy is checked against D-088's size and SHA-256 before
anything reads it, so OpenCV only ever parses these exact files, and the worker
refuses to start without them where `FACEMATCH_PROVIDER` is `sface`.

`python -m app.core.facemodels [dir]` fetches into `dir` (default `MODEL_DIR`).
It imports nothing from the app, so the Dockerfile runs it as a plain file
before the app's code is copied in, and a code change doesn't fetch 39 MB again.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import httpx

# api/models locally; /app/models in the image (the app is /app/app).
MODEL_DIR: Final = Path(__file__).resolve().parents[2] / "models"

# OpenCV Zoo's main branch on 28 May 2026. The hashes decide; the commit only
# keeps the URLs from moving under us.
_ZOO: Final = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/"
    "47534e27c9851bb1128ccc0102f1145e27f23f98/models"
)


@dataclass(frozen=True)
class Model:
    name: str
    url: str
    size: int
    sha256: str


# D-088's sizes and SHA-256s: the Zoo's Git LFS records, and what was fetched
# from these URLs on 5 October 2026.
DETECTOR: Final = Model(
    name="face_detection_yunet_2023mar.onnx",
    url=f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    size=232_589,
    sha256="8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
)
RECOGNIZER: Final = Model(
    name="face_recognition_sface_2021dec.onnx",
    url=f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    size=38_696_353,
    sha256="0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
)
MODELS: Final = (DETECTOR, RECOGNIZER)

_CHUNK = 1 << 20


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def problems(model_dir: Path | None = None) -> list[str]:
    """What is wrong with the models in `model_dir` (`MODEL_DIR` unless
    given), one line each, naming the file: missing, the wrong size, or the
    wrong SHA-256. Empty when both are exactly D-088's."""
    model_dir = model_dir or MODEL_DIR
    found: list[str] = []
    for model in MODELS:
        path = model_dir / model.name
        if not path.is_file():
            found.append(f"{model.name} is missing from {model_dir}")
        elif wrong := problems_with(model, path):
            found.append(f"{model.name} is {wrong}")
    return found


async def fetch(
    model_dir: Path, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """Fetch each model `model_dir` doesn't already hold exactly. A download is
    checked before it takes the model's name, so a failed or altered one never
    sits where the worker looks."""
    model_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=120, transport=transport
    ) as client:
        for model in MODELS:
            path = model_dir / model.name
            if path.is_file() and not problems_with(model, path):
                continue
            partial = path.with_name(path.name + ".part")
            async with client.stream("GET", model.url) as response:
                response.raise_for_status()
                with partial.open("wb") as file:
                    async for chunk in response.aiter_bytes(_CHUNK):
                        file.write(chunk)
            wrong = problems_with(model, partial)
            if wrong:
                partial.unlink()
                raise ValueError(f"{model.name} from {model.url}: {wrong}")
            partial.replace(path)


def problems_with(model: Model, path: Path) -> str | None:
    if path.stat().st_size != model.size:
        return f"{path.stat().st_size} bytes, not {model.size}"
    if _sha256(path) != model.sha256:
        return "not D-088's SHA-256"
    return None


def main(argv: list[str]) -> int:
    model_dir = Path(argv[0]) if argv else MODEL_DIR
    asyncio.run(fetch(model_dir))
    sys.stdout.write(f"facemodels: both models in {model_dir}, as D-088 records.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
