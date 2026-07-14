# syntax=docker/dockerfile:1

# ---- Stage 1: build the virtualenv with uv ----------------------------------
FROM python:3.12-slim AS builder

# uv: fast, reproducible installs from uv.lock
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install deps first (cached layer) using only the lock + manifest.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra assets --extra notion

# Now install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra assets --extra notion

# ---- Stage 2: slim runtime image --------------------------------------------
FROM python:3.12-slim AS runtime

# matplotlib (assets extra) needs libgomp; curl is for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

# Copy the resolved venv and the application code from the builder.
COPY --from=builder --chown=appuser:appuser /app /app

# Put the venv on PATH so `streamlit`/`note-agent` resolve directly.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Persisted outputs: notes, run logs and the retrieval cache.
RUN mkdir -p /app/notes /app/runs /app/.cache && chown -R appuser:appuser /app/notes /app/runs /app/.cache
VOLUME ["/app/notes", "/app/runs", "/app/.cache"]

USER appuser
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

# Default: the Streamlit UI. Override with e.g. `note-agent` for the CLI.
CMD ["streamlit", "run", "app.py"]
