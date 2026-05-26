# Dashboard service — judge-facing UI + Agent SRE pipeline orchestrator.
# Single-stage Python 3.12 image with uv for dependency management.
#
# Build:   docker build -t agent-sre-dashboard .
# Run:     docker run -p 8080:8080 -e GOOGLE_API_KEY=... -e PHOENIX_BASE_URL=... agent-sre-dashboard

FROM python:3.12-slim

# Copy uv binary from the official image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install Python deps first so this layer caches across source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source.
COPY shared/        ./shared/
COPY target_agent/  ./target_agent/
COPY agent_sre/     ./agent_sre/
COPY dashboard/     ./dashboard/
COPY scripts/       ./scripts/
COPY README.md      LICENSE  ./

# Install our package itself now that source is present.
RUN uv sync --frozen --no-dev

# Cloud Run injects PORT (defaults to 8080). The dashboard binds to it.
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn dashboard.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
