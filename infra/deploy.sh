#!/usr/bin/env bash
# Deploy Agent SRE (Phoenix + Dashboard) to Cloud Run.
#
# Usage:
#   GOOGLE_CLOUD_PROJECT=your-project-id ./infra/deploy.sh
#
# Optional env vars:
#   GOOGLE_CLOUD_LOCATION  (default: us-central1)
#   GOOGLE_API_KEY         (auto-detected from .env if not set)
#
# What it does:
#   1. Verifies gcloud auth + project
#   2. Enables Cloud Run + Cloud Build + Artifact Registry APIs
#   3. Builds & deploys Phoenix as a Cloud Run service
#   4. Builds & deploys the Dashboard as a Cloud Run service, with Phoenix URL wired in
#   5. Prints both URLs — the Dashboard URL is what judges hit

set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_PHOENIX="${SERVICE_PHOENIX:-agent-sre-phoenix}"
SERVICE_DASHBOARD="${SERVICE_DASHBOARD:-agent-sre-dashboard}"

if [ -z "$PROJECT" ]; then
  echo "ERROR: GOOGLE_CLOUD_PROJECT is required."
  echo "Example: GOOGLE_CLOUD_PROJECT=agent-sre-hackathon ./infra/deploy.sh"
  exit 1
fi

# Try to source GOOGLE_API_KEY from .env if not in env already.
API_KEY="${GOOGLE_API_KEY:-}"
if [ -z "$API_KEY" ] && [ -f .env ]; then
  API_KEY=$(grep -E '^GOOGLE_API_KEY=' .env | head -n1 | cut -d'=' -f2- | tr -d '"' | tr -d "'")
fi
if [ -z "$API_KEY" ]; then
  echo "ERROR: GOOGLE_API_KEY is required (set env or include in .env)."
  exit 1
fi

# Models — match what the dashboard expects. Override via env if you want different ones.
PLANNER_MODEL="${GEMINI_PLANNER_MODEL:-gemini-3.1-flash-lite}"
WORKER_MODEL="${GEMINI_WORKER_MODEL:-gemini-3.1-flash-lite}"
PHOENIX_PROJECT_NAME="${PHOENIX_PROJECT_NAME:-match2026-travel}"

echo "============================================================"
echo "Agent SRE — Cloud Run deployment"
echo "  Project:       $PROJECT"
echo "  Region:        $REGION"
echo "  Phoenix svc:   $SERVICE_PHOENIX"
echo "  Dashboard svc: $SERVICE_DASHBOARD"
echo "  Planner model: $PLANNER_MODEL"
echo "  Worker model:  $WORKER_MODEL"
echo "============================================================"

echo ""
echo "==> Setting active gcloud project"
gcloud config set project "$PROJECT" --quiet

echo ""
echo "==> Enabling required APIs (idempotent; this is fast if already enabled)"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project "$PROJECT" --quiet

echo ""
echo "==> [1/2] Deploying Phoenix to Cloud Run..."
gcloud run deploy "$SERVICE_PHOENIX" \
  --source infra/phoenix \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --min-instances 0 \
  --max-instances 1 \
  --project "$PROJECT" \
  --quiet

PHOENIX_URL=$(gcloud run services describe "$SERVICE_PHOENIX" \
  --region "$REGION" --format='value(status.url)' --project "$PROJECT")

echo ""
echo "    Phoenix deployed at: $PHOENIX_URL"

echo ""
echo "==> [2/2] Deploying Dashboard to Cloud Run..."

# Build env-var string. Phoenix self-hosted has no auth, but our code requires
# PHOENIX_API_KEY to be non-empty — we use a sentinel value.
ENV_VARS="GOOGLE_API_KEY=$API_KEY"
ENV_VARS="$ENV_VARS,GOOGLE_CLOUD_PROJECT=$PROJECT"
ENV_VARS="$ENV_VARS,GOOGLE_CLOUD_LOCATION=$REGION"
ENV_VARS="$ENV_VARS,PHOENIX_BASE_URL=$PHOENIX_URL"
ENV_VARS="$ENV_VARS,PHOENIX_COLLECTOR_ENDPOINT=$PHOENIX_URL/v1/traces"
ENV_VARS="$ENV_VARS,PHOENIX_API_KEY=cloud-run-self-hosted"
ENV_VARS="$ENV_VARS,PHOENIX_PROJECT_NAME=$PHOENIX_PROJECT_NAME"
ENV_VARS="$ENV_VARS,GEMINI_PLANNER_MODEL=$PLANNER_MODEL"
ENV_VARS="$ENV_VARS,GEMINI_WORKER_MODEL=$WORKER_MODEL"

gcloud run deploy "$SERVICE_DASHBOARD" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars "$ENV_VARS" \
  --project "$PROJECT" \
  --quiet

DASHBOARD_URL=$(gcloud run services describe "$SERVICE_DASHBOARD" \
  --region "$REGION" --format='value(status.url)' --project "$PROJECT")

echo ""
echo "============================================================"
echo "✓ Deployment complete"
echo "============================================================"
echo "  Phoenix:    $PHOENIX_URL"
echo "  Dashboard:  $DASHBOARD_URL  ← judges go here"
echo ""
echo "Next: seed traces into the deployed Phoenix so the demo has data."
echo "Run from your local machine:"
echo "  PHOENIX_BASE_URL=$PHOENIX_URL PHOENIX_COLLECTOR_ENDPOINT=$PHOENIX_URL/v1/traces \\"
echo "    uv run python -m scripts.seed_failures"
echo ""
