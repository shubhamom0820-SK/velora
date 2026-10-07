"""T-4.11's liveness research, as a probe anyone can run again (D-381).

The numbers T-4.11 and D-380 cite were measured with this code on 5 October
2026: what MiniFASNet costs in memory beside the worker's own face matching
(`probe.py`), and that the third-party ONNX files are minivision's weights
(`same_weights.py`). Both run inside the API image, as the worker does.

From the repository's root, with Docker:

    docker build -t velora-api:bench api
    docker build -t velora-api:bench-tools --build-arg BASE=velora-api:bench api/bench/liveness
    (cd api && uv run python -m bench.liveness.weights)
    (cd api && uv run python -m bench.liveness.run all)

- `weights` fetches MiniFASNet's files into `out/t-4.11-probe/weights/`, each
  checked by size and SHA-256 before anything reads it. YuNet and SFace come
  from the API image, which fetches and checks its own (D-088).
- `run` starts each run in a fresh container as Fly runs the worker (one CPU,
  1 GB, no swap) and keeps its output in `out/t-4.11-probe/logs/`. Its faces
  are the NASA fixtures unless `--faces` names a directory outside the
  repository: inside it, it refuses (`run.faces_dir`).
- `velora-api:bench-tools` adds torch and onnxruntime, for two routes and the
  weights check. This directory's Dockerfile is the only place they exist
  (D-381).

Never in the image (`api/.dockerignore`), never run by `make test`: it needs
Docker, a 1 GB cap and downloads. Not a Makefile target, by the founder's
choice (7 October 2026): until running it is routine work, this is enough.
"""
