"""What MiniFASNet costs in memory beside the worker's own face matching
(T-4.11). Runs inside the API image, started by `run.py`, never by hand.

One route a process. Each stage prints the process's resident memory now
(VmRSS) and its peak since it started (VmHWM), in MB, read from
/proc/self/status; the last line is `RESULT {json}`. The comparison is the
worker's own: `SFaceFaceMatch.compare` on a selfie and two photos, each a
fixture enlarged to 1,600 pixels and re-encoded as the pipeline re-encodes
(as T-4.5's probe on Fly did), and then the route's liveness score on the
selfie, 22 times; or, with `--at-once N`, N threads each with its own set of
models (OpenCV's model objects aren't shared across threads), 5 times each.

Routes: `baseline` (face matching alone), `minifas_cv` (MiniFASNet through
OpenCV's DNN, the image's own), `minifas_ort` (the same files through
onnxruntime) and `minifas_torch` (minivision's `.pth` and code through
PyTorch). The last two need the bench-tools image (D-381).
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Protocol

if TYPE_CHECKING:
    import numpy as np

    from app.core.providers.facematch import SFaceFaceMatch

ROUTES: Final = ("baseline", "minifas_cv", "minifas_ort", "minifas_torch")
# minivision's pair: each network and the scale of its crop around the face.
PAIR: Final = (
    ("yakhyo_MiniFASNetV2.onnx", "2.7_80x80_MiniFASNetV2.pth", "MiniFASNetV2", 2.7),
    (
        "yakhyo_MiniFASNetV1SE.onnx",
        "4_0_0_80x80_MiniFASNetV1SE.pth",
        "MiniFASNetV1SE",
        4.0,
    ),
)
REAL: Final = 1  # minivision's classes: 0 a 2D fake, 1 real, 2 a 3D fake

LOG: list[dict[str, Any]] = []


def say(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def memory_mb() -> dict[str, int]:
    found = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith(("VmRSS", "VmHWM")):
            key, value = line.split(":")
            found[key] = int(value.split()[0]) // 1024
    return found


def stage(name: str, **extra: Any) -> None:
    row = {"stage": name, **memory_mb(), **extra}
    LOG.append(row)
    say(json.dumps(row))


def crop_minifas(bgr: np.ndarray, box: Any, scale: float) -> np.ndarray:
    """minivision's `CropImage._get_new_box` and `crop`, the same arithmetic:
    the face's box scaled about its centre, pushed back inside the image, and
    resized to 80 by 80."""
    import cv2

    src_h, src_w = bgr.shape[:2]
    x, y, box_w, box_h = (float(v) for v in box[:4])
    scale = min((src_h - 1) / box_h, min((src_w - 1) / box_w, scale))
    new_w, new_h = box_w * scale, box_h * scale
    centre_x, centre_y = box_w / 2 + x, box_h / 2 + y
    left, top = centre_x - new_w / 2, centre_y - new_h / 2
    right, bottom = centre_x + new_w / 2, centre_y + new_h / 2
    if left < 0:
        right -= left
        left = 0
    if top < 0:
        bottom -= top
        top = 0
    if right > src_w - 1:
        left -= right - src_w + 1
        right = src_w - 1
    if bottom > src_h - 1:
        top -= bottom - src_h + 1
        bottom = src_h - 1
    patch = bgr[int(top) : int(bottom) + 1, int(left) : int(right) + 1]
    resized: np.ndarray = cv2.resize(patch, (80, 80))
    return resized


def blob(patch: np.ndarray) -> np.ndarray:
    """As minivision feeds it: channels first, 0 to 255, never divided."""
    import numpy as np

    shaped: np.ndarray = patch.transpose(2, 0, 1)[None].astype(np.float32)
    return shaped


def softmax(values: np.ndarray) -> np.ndarray:
    import numpy as np

    exp = np.exp(values - values.max())
    out: np.ndarray = exp / exp.sum()
    return out


class Liveness(Protocol):
    def load(self) -> None: ...

    def score(self, bgr: np.ndarray, box: Any) -> float: ...


class MiniFASCv:
    """The pair through OpenCV's DNN: nothing the image doesn't have."""

    def __init__(self, weights: Path) -> None:
        self.weights = weights
        self.nets: list[tuple[Any, float]] = []

    def load(self) -> None:
        import cv2

        self.nets = [
            (cv2.dnn.readNetFromONNX(str(self.weights / onnx)), scale)
            for onnx, _, _, scale in PAIR
        ]

    def forward(self, net: Any, data: np.ndarray) -> np.ndarray:
        net.setInput(data)
        out: np.ndarray = net.forward()
        return out

    def score(self, bgr: np.ndarray, box: Any) -> float:
        import numpy as np

        total = np.zeros(3)
        for net, scale in self.nets:
            out = self.forward(net, blob(crop_minifas(bgr, box, scale)))
            total += softmax(np.asarray(out).reshape(-1))
        return float(total[REAL] / len(self.nets))


class MiniFASOrt(MiniFASCv):
    """The same two files through onnxruntime (bench-tools only, D-381)."""

    def load(self) -> None:
        import onnxruntime

        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = 1
        self.nets = [
            (
                onnxruntime.InferenceSession(
                    str(self.weights / onnx),
                    options,
                    providers=["CPUExecutionProvider"],
                ),
                scale,
            )
            for onnx, _, _, scale in PAIR
        ]

    def forward(self, net: Any, data: np.ndarray) -> np.ndarray:
        out: np.ndarray = net.run(None, {net.get_inputs()[0].name: data})[0]
        return out


class MiniFASTorch(MiniFASCv):
    """minivision's own `.pth` files and network code through PyTorch: the
    route minivision's `test.py` and DeepFace take (bench-tools only, D-381).
    `weights_only=True`: a `.pth` is a pickle, which can run code as it loads."""

    def load(self) -> None:
        import torch

        sys.path.insert(0, str(self.weights))
        import MiniFASNet  # minivision's src/model_lib/MiniFASNet.py, fetched

        self.torch = torch
        self.nets = []
        for _, pth, network, scale in PAIR:
            model = getattr(MiniFASNet, network)(conv6_kernel=(5, 5))
            state = torch.load(
                self.weights / pth, map_location="cpu", weights_only=True
            )
            model.load_state_dict(
                {k.removeprefix("module."): v for k, v in state.items()}
            )
            model.eval()
            self.nets.append((model, scale))

    def forward(self, net: Any, data: np.ndarray) -> np.ndarray:
        with self.torch.no_grad():
            out: np.ndarray = net(self.torch.from_numpy(data)).numpy()
        return out


def route(name: str, weights: Path) -> Liveness:
    """The route's liveness check, not yet loaded (`baseline` has none)."""
    if name == "minifas_ort":
        return MiniFASOrt(weights)
    if name == "minifas_torch":
        return MiniFASTorch(weights)
    return MiniFASCv(weights)


def enlarged(faces: Path, name: str) -> bytes:
    """A fixture enlarged to 1,600 pixels on its longest side, then re-encoded
    exactly as the pipeline does.

    **Line for line as 5 October 2026's probe wrote it, and it must stay so:**
    each step inside the `with`, each image dropped as the next is made. The
    probe's baseline varies 392 to 406 MB from run to run with no code change
    (20 runs, 7 October 2026), so a version of this function that frees its images in
    another order is a different probe, whose readings would have to be shown
    to fall in the recorded range again before they could stand beside it."""
    from PIL import Image

    from app.core.images import reencode

    with Image.open(faces / name) as opened:
        im: Image.Image = opened
        im = im.convert("RGB")
        scale = 1600 / max(im.size)
        im = im.resize(
            (round(im.width * scale), round(im.height * scale)),
            Image.Resampling.LANCZOS,
        )
        raw = io.BytesIO()
        im.save(raw, "JPEG", quality=95)
    return reencode(raw.getvalue(), "image/jpeg").data


def one_pipeline(
    facematch: SFaceFaceMatch,
    live: Liveness | None,
    selfie: bytes,
    refs: list[bytes],
) -> dict[str, Any]:
    from app.core.providers.facematch import _pixels

    match = asyncio.run(facematch.compare(selfie, refs))
    out: dict[str, Any] = {
        "faces": match.faces_in_selfie,
        "sims": [None if s is None else round(s, 4) for s in match.similarities],
    }
    if live is not None:
        bgr = _pixels(selfie)  # as compare decodes it: Pillow, then BGR pixels
        # The face compare found, by the worker's own detector.
        out["live"] = round(live.score(bgr, facematch._faces(bgr)[0]), 4)
    return out


def main(argv: list[str]) -> int:
    # 5 October 2026's order, which the numbers depend on: the first stage,
    # then the same imports, then the second.
    stage("python started")
    import numpy  # noqa: F401
    from PIL import Image  # noqa: F401

    from app.core.images import reencode  # noqa: F401
    from app.core.providers.facematch import SFaceFaceMatch, _pixels  # noqa: F401

    stage("app imports (numpy, Pillow, app.core)")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("route", choices=ROUTES)
    parser.add_argument("--at-once", type=int, default=1)
    parser.add_argument("--faces", type=Path, default=Path("/faces"))
    parser.add_argument("--weights", type=Path, default=Path("/weights"))
    parser.add_argument("--selfie", default="chari_2021.jpg")
    parser.add_argument(
        "--refs", nargs="+", default=["chari_2017.jpg", "williams_2004.jpg"]
    )
    args = parser.parse_args(argv)
    import cv2

    stage("cv2 imported", threads=cv2.getNumThreads())
    selfie = enlarged(args.faces, args.selfie)
    refs = [enlarged(args.faces, name) for name in args.refs]
    stage(f"{1 + len(refs)} 1,600-px JPEGs re-encoded")

    sets: list[tuple[SFaceFaceMatch, Liveness | None]] = []
    for _ in range(args.at_once):
        facematch = SFaceFaceMatch()  # the image's own models, checked (D-088)
        facematch.load()
        sets.append((facematch, None))
    stage("YuNet + SFace loaded", copies=args.at_once)
    if args.route != "baseline":
        for n, (facematch, _) in enumerate(sets):
            loaded = route(args.route, args.weights)
            loaded.load()
            sets[n] = (facematch, loaded)
        stage(f"{args.route} loaded", copies=args.at_once)

    if args.at_once == 1:
        facematch, live = sets[0]
        started = time.perf_counter()
        result = one_pipeline(facematch, live, selfie, refs)
        took = round((time.perf_counter() - started) * 1000)
        stage("first compare + liveness", ms=took, **result)
        for _ in range(20):
            one_pipeline(facematch, live, selfie, refs)
        started = time.perf_counter()
        result = one_pipeline(facematch, live, selfie, refs)
        took = round((time.perf_counter() - started) * 1000)
        stage("after 22 runs", ms=took, **result)
    else:
        barrier = threading.Barrier(args.at_once)

        def worker(facematch: SFaceFaceMatch, live: Liveness | None) -> None:
            barrier.wait()
            for _ in range(5):
                one_pipeline(facematch, live, selfie, refs)

        threads = [threading.Thread(target=worker, args=pair) for pair in sets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stage(f"{args.at_once} at once, 5 runs each")
    result_line = {
        "route": args.route,
        "at_once": args.at_once,
        "peak_mb": LOG[-1]["VmHWM"],
        "stages": LOG,
    }
    say("RESULT " + json.dumps(result_line))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
