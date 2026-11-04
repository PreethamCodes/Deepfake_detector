# SHODHA AI backend: FastAPI with D³, GenD and AASIST on CPU.
# Used by compose.yaml for local runs and copied into the Hugging Face Space by
# deploy/huggingface/prepare_space.ps1.
FROM python:3.11-slim

# git: uv.lock installs OpenAI CLIP from GitHub. libglib2.0-0: OpenCV runtime dependency.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /uvx /bin/

# Hugging Face Spaces run the container as user 1000; using it everywhere keeps file ownership consistent.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# Dependencies first so code changes reuse the cached layer.
COPY --chown=user pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --all-extras --no-dev --no-install-project

# Download and hash-verify the official weights at build time (about 2.2 GB).
# They live in the image only and are never committed or redistributed.
COPY --chown=user truthscan/models truthscan/models
COPY --chown=user truthscan/__init__.py truthscan/__init__.py
RUN .venv/bin/python -m truthscan.models.image.weights \
 && .venv/bin/python -m truthscan.models.video.weights \
 && .venv/bin/python -m truthscan.models.audio.weights

COPY --chown=user . .
RUN uv sync --locked --all-extras --no-dev && mkdir -p data/api

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD [".venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD [".venv/bin/python", "-m", "uvicorn", "truthscan.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
