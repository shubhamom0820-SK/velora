# The bench-tools image (T-4.11, D-381): the API image, plus torch and
# onnxruntime for two of the probe's routes and the weights check. This file is
# the only place either is installed: never in uv.lock, never in the API image
# (tests/bench/liveness/test_bench_only.py; CI looks inside the built image).
# A .pth file is a pickle, which can run code as it loads: it has no business
# in production.
#
#   docker build -t velora-api:bench api
#   docker build -t velora-api:bench-tools --build-arg BASE=velora-api:bench api/bench/liveness
#
# The versions are those measured on 5 October 2026. torch from PyTorch's own
# CPU index: PyPI's Linux build pulls CUDA's libraries with it.
ARG BASE=velora-api:bench
FROM ${BASE}
USER root
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /bin/uv
RUN uv pip install --python /app/.venv/bin/python onnxruntime==1.30.0
RUN uv pip install --python /app/.venv/bin/python --index-url https://download.pytorch.org/whl/cpu torch==2.14.1
USER app
