"""Are the third-party ONNX files minivision's weights? (T-4.11, D-088's
standard: the weights we would run are the ones whose licence was read.)

Each ONNX file runs through OpenCV's DNN beside minivision's own `.pth` through
its own network code (PyTorch), on the same inputs: 500 random 80-by-80
patches (seed 0) and every face YuNet finds in `--faces`, cropped at the
network's scale. Prints the largest difference between their softmax outputs.
Runs inside the bench-tools image (D-381), started by `run.py`.

The faces are read with OpenCV's decoder, as on 5 October 2026, so the run
reproduces that day's numbers; they are fixtures or a consenting set, never an
upload (D-092 keeps OpenCV's decoders away from uploads, in the worker).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Final

from bench.liveness.probe import PAIR, blob, crop_minifas, say, softmax

GARCIAFIDO: Final = "garciafido_minifasnet_v2.onnx"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--faces", type=Path, default=Path("/faces"))
    parser.add_argument("--weights", type=Path, default=Path("/weights"))
    args = parser.parse_args(argv)
    weights: Path = args.weights

    import cv2
    import numpy as np
    import torch

    from app.core import facemodels
    from app.core.providers.facematch import DETECTION_SCORE

    sys.path.insert(0, str(weights))
    import MiniFASNet  # minivision's src/model_lib/MiniFASNet.py, fetched

    def network(name: str, pth: str) -> Any:
        model = getattr(MiniFASNet, name)(conv6_kernel=(5, 5))
        # A .pth is a pickle: weights_only refuses anything but tensors.
        state = torch.load(weights / pth, map_location="cpu", weights_only=True)
        model.load_state_dict({k.removeprefix("module."): v for k, v in state.items()})
        model.eval()
        return model

    (v2_onnx, v2_pth, v2, v2_scale), (v1se_onnx, v1se_pth, v1se, v1se_scale) = PAIR
    pairs = [
        ("MiniFASNetV2 yakhyo", network(v2, v2_pth), v2_onnx, v2_scale),
        ("MiniFASNetV2 garciafido", network(v2, v2_pth), GARCIAFIDO, v2_scale),
        ("MiniFASNetV1SE yakhyo", network(v1se, v1se_pth), v1se_onnx, v1se_scale),
    ]

    rng = np.random.default_rng(0)
    patches = [rng.integers(0, 256, (80, 80, 3), dtype=np.uint8) for _ in range(500)]
    detector = cv2.FaceDetectorYN.create(
        str(facemodels.MODEL_DIR / facemodels.DETECTOR.name),
        "",
        (320, 320),
        DETECTION_SCORE,
        0.3,
        5000,
    )
    faces = []
    for path in sorted(args.faces.glob("*.jpg")):
        image = cv2.imread(str(path))
        if image is None:
            raise SystemExit(f"same_weights: {path} isn't an image OpenCV can read.")
        detector.setInputSize((image.shape[1], image.shape[0]))
        _, found = detector.detect(image)
        for face in found if found is not None else []:
            faces.append((image, face))
    say(f"{len(patches)} random patches, {len(faces)} faces from {args.faces}")

    worst_of_all = 0.0
    for name, model, onnx, scale in pairs:
        net = cv2.dnn.readNetFromONNX(str(weights / onnx))
        inputs = patches + [crop_minifas(image, face, scale) for image, face in faces]
        worst = 0.0
        for patch in inputs:
            data = blob(patch)
            with torch.no_grad():
                theirs = softmax(model(torch.from_numpy(data)).numpy().reshape(-1))
            net.setInput(data)
            ours = softmax(np.asarray(net.forward()).reshape(-1))
            worst = max(worst, float(np.abs(theirs - ours).max()))
        worst_of_all = max(worst_of_all, worst)
        say(
            f"{name:26} vs minivision .pth: largest softmax difference "
            f"over {len(inputs)} inputs = {worst:.2e}"
        )
    say(f"RESULT {worst_of_all:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
