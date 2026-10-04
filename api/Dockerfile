# The API image (T-1.22). Built with api/ as the context; api/.dockerignore keeps
# every .env out (P-32). Two stages: uv builds the virtualenv from uv.lock, and
# the runtime stage copies only that and the code, and runs as a non-root user.
# Base images are pinned by digest, so a rebuild can't pick up a different one.

FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so a code-only change reuses this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
# The face models (D-088, T-4.5): fetched from OpenCV Zoo at a pinned commit and
# checked against D-088's sizes and SHA-256s, never committed; the worker
# refuses to start without exactly these. Before the code, so a code change
# doesn't fetch 39 MB again. api/.dockerignore keeps any local copy out.
COPY app/core/facemodels.py app/core/facemodels.py
RUN .venv/bin/python app/core/facemodels.py
COPY . .
RUN uv sync --locked --no-dev

FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
RUN groupadd --system app && useradd --system --gid app --no-create-home app
WORKDIR /app
COPY --from=build --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
# Settings are checked once, before any worker starts: uvicorn restarts workers
# that die, so a configuration error (a missing variable, a fake provider outside
# local) would otherwise crash-loop forever inside a "running" machine instead
# of stopping it with the message.
#
# 0.0.0.0 inside the container: Fly's proxy reaches the app over the machine's
# private network. Two workers, each with its own database pool — size the pool
# for both (DB_POOL_SIZE, DB_MAX_OVERFLOW; infra/STAGING.md). The proxy sets
# X-Forwarded-*, and nothing else can reach the machine.
CMD ["sh", "-c", "python -c 'from app.core.config import get_settings; get_settings()' && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips '*'"]
