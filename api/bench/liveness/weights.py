"""The liveness candidate's files (T-4.11): where they come from, what they must
be, and fetching them.

MiniFASNet, minivision's Silent-Face-Anti-Spoofing, Apache-2.0: its two
`.pth` checkpoints and the one file of its code that builds the networks, at
the commit the research read (5 October 2026); and two third-party ONNX
exports of the same weights, which `same_weights.py` holds to them. Each is
checked against its size and SHA-256 before anything reads it, as D-088's face
models are, and none is committed. YuNet and SFace aren't here: the API image
fetches and checks its own (`app.core.facemodels`).

    uv run python -m bench.liveness.weights [dir]    # from api/

`dir` defaults to `out/t-4.11-probe/weights/`, git-ignored.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Final

import httpx

from app.core.facemodels import Model, problems_with

REPO: Final = Path(__file__).resolve().parents[3]
WEIGHTS_DIR: Final = REPO / "out" / "t-4.11-probe" / "weights"

# minivision-ai/Silent-Face-Anti-Spoofing's master on 5 August 2020: the
# commit whose LICENSE (Apache-2.0, "Copyright 2020 Minivision") the research
# read. These files are in the repository itself, not Git LFS.
_MINIVISION: Final = (
    "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/"
    "b6d5f04ad78778917853b25c778acef6d5626d15"
)
# yakhyo/face-anti-spoofing's release `weights`. A release's files can be
# replaced, so the SHA-256 decides, not the URL.
_YAKHYO: Final = (
    "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights"
)
# garciafido/minifasnet-v2-anti-spoofing-onnx on Hugging Face, at a revision.
_GARCIAFIDO: Final = (
    "https://huggingface.co/garciafido/minifasnet-v2-anti-spoofing-onnx/resolve/"
    "d29c87568ca9b5662da803b10f217c4db20b142b"
)

V2_PTH: Final = Model(
    name="2.7_80x80_MiniFASNetV2.pth",
    url=f"{_MINIVISION}/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth",
    size=1_849_453,
    sha256="a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0",
)
V1SE_PTH: Final = Model(
    name="4_0_0_80x80_MiniFASNetV1SE.pth",
    url=f"{_MINIVISION}/resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth",
    size=1_856_130,
    sha256="84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990",
)
# The networks' code: imports torch and nothing else of minivision's.
NETWORKS: Final = Model(
    name="MiniFASNet.py",
    url=f"{_MINIVISION}/src/model_lib/MiniFASNet.py",
    size=12_487,
    sha256="e498c4ec5e1ddfaba62b941a126c19d65aa564999f3309661fe43ee8bf38acd7",
)
V2_ONNX: Final = Model(
    name="yakhyo_MiniFASNetV2.onnx",
    url=f"{_YAKHYO}/MiniFASNetV2.onnx",
    size=1_743_581,
    sha256="b32929adc2d9c34b9486f8c4c7bc97c1b69bc0ea9befefc380e4faae4e463907",
)
V1SE_ONNX: Final = Model(
    name="yakhyo_MiniFASNetV1SE.onnx",
    url=f"{_YAKHYO}/MiniFASNetV1SE.onnx",
    size=1_742_335,
    sha256="ebab7f90c7833fbccd46d3a555410e78d969db5438e169b6524be444862b3676",
)
GARCIAFIDO_V2_ONNX: Final = Model(
    name="garciafido_minifasnet_v2.onnx",
    url=f"{_GARCIAFIDO}/minifasnet_v2.onnx",
    size=1_744_116,
    sha256="d7b3cd9ba8a7ceb13baa8c4720902e27ca3112eff52f926c08804af6b6eecc7b",
)
FILES: Final = (V2_PTH, V1SE_PTH, NETWORKS, V2_ONNX, V1SE_ONNX, GARCIAFIDO_V2_ONNX)

_CHUNK = 1 << 20


def problems(weights_dir: Path) -> list[str]:
    """What is wrong with the files in `weights_dir`, one line each, naming the
    file. Empty when every one is exactly as above."""
    found: list[str] = []
    for model in FILES:
        path = weights_dir / model.name
        if not path.is_file():
            found.append(f"{model.name} is missing from {weights_dir}")
        elif wrong := problems_with(model, path):
            found.append(f"{model.name} is {wrong}")
    return found


async def fetch(weights_dir: Path) -> None:
    """Fetch each file `weights_dir` doesn't already hold exactly. A download
    is checked before it takes the file's name, so a failed or altered one
    never sits where the probe looks."""
    weights_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        for model in FILES:
            path = weights_dir / model.name
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


def main(argv: list[str]) -> int:
    weights_dir = Path(argv[0]) if argv else WEIGHTS_DIR
    asyncio.run(fetch(weights_dir))
    sys.stdout.write(f"weights: all {len(FILES)} files in {weights_dir}, checked.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
