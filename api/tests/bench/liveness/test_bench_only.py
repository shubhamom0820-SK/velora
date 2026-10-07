"""D-381: torch and onnxruntime, the liveness probe's tools, live in
`api/bench/liveness/Dockerfile` and nowhere else: never in uv.lock, never in
the API image. A `.pth` file is a pickle, which can run code as it loads.

Each test closes one way in: the lock (all `uv sync --locked` installs), any
other install in the API's Dockerfile, and the bench's own code, which imports
them (`api/.dockerignore`). CI's `scripts/check-image-no-bench-tools` looks
inside the built image itself.
"""

from __future__ import annotations

import tomllib

from tests.infra import API_DIR

BENCH_ONLY = ("torch", "onnxruntime")

# Every RUN in the API's Dockerfile, exactly: the image installs what uv.lock
# says and nothing else. A new RUN is a change this list has to name.
API_IMAGE_RUNS = (
    "uv sync --locked --no-dev --no-install-project",
    ".venv/bin/python app/core/facemodels.py",
    "uv sync --locked --no-dev",
    "groupadd --system app && useradd --system --gid app --no-create-home app",
)


def bench_only(name: str) -> bool:
    """torch or onnxruntime, and their variants (torchvision, onnxruntime-gpu)."""
    return name.lower().startswith(BENCH_ONLY)


def test_the_lock_holds_no_bench_only_package() -> None:
    lock = tomllib.loads((API_DIR / "uv.lock").read_text())
    names = [package["name"] for package in lock["package"]]

    assert "opencv-python-headless" in names  # it read the real lock
    assert [name for name in names if bench_only(name)] == []


def test_the_api_image_installs_only_the_lock() -> None:
    lines = (API_DIR / "Dockerfile").read_text().splitlines()
    runs = tuple(line.removeprefix("RUN ") for line in lines if line.startswith("RUN "))

    assert runs == API_IMAGE_RUNS
    assert [line for line in lines if bench_only_mentioned(line)] == []


def bench_only_mentioned(line: str) -> bool:
    return any(name in line.lower() for name in BENCH_ONLY)


def test_the_bench_never_enters_the_api_image() -> None:
    ignored = (API_DIR / ".dockerignore").read_text().splitlines()

    assert "bench" in ignored


def test_the_bench_tools_image_pins_what_was_measured() -> None:
    dockerfile = (API_DIR / "bench" / "liveness" / "Dockerfile").read_text()

    assert "onnxruntime==1.30.0" in dockerfile
    assert (
        "--index-url https://download.pytorch.org/whl/cpu torch==2.14.1" in dockerfile
    )
