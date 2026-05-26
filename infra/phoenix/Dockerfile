# Self-hosted Phoenix instance for Cloud Run.
#
# Phoenix's default SQLite store is ephemeral on Cloud Run's filesystem — fine for
# demo / hackathon use (we re-seed traces between sessions). For long-running prod,
# bind Phoenix to Cloud SQL via PHOENIX_SQL_DATABASE_URL.
#
# Build:   docker build -t agent-sre-phoenix -f infra/phoenix/Dockerfile infra/phoenix
# Run:     docker run -p 8080:8080 agent-sre-phoenix

FROM python:3.12-slim

# Phoenix is published as a regular Python package; no compilers needed at runtime.
RUN pip install --no-cache-dir \
        'arize-phoenix>=7.0' \
        'arize-phoenix-client>=2.7.0' \
        'arize-phoenix-otel>=0.16.0'

# Cloud Run injects PORT; Phoenix reads PHOENIX_PORT.
ENV PHOENIX_HOST=0.0.0.0
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "PHOENIX_PORT=${PORT:-8080} phoenix serve"]
