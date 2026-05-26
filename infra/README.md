# Deployment — Agent SRE on Cloud Run

This directory contains everything needed to deploy Agent SRE (Dashboard + self-hosted Phoenix) to Google Cloud Run.

## Architecture

Two Cloud Run services:

| Service | URL | Purpose |
|---|---|---|
| `agent-sre-phoenix`   | `https://agent-sre-phoenix-<hash>-uc.a.run.app`   | Self-hosted Arize Phoenix instance (traces + datasets) |
| `agent-sre-dashboard` | `https://agent-sre-dashboard-<hash>-uc.a.run.app` | Judge-facing UI + 8-phase pipeline orchestrator |

The Dashboard talks to Phoenix over HTTPS. Phoenix stores traces in ephemeral SQLite — fine for hackathon demos (seed once per session). For long-running prod, bind Phoenix to Cloud SQL via `PHOENIX_SQL_DATABASE_URL`.

## Prerequisites

1. **gcloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   ```
2. **A GCP project with billing enabled.** Cloud Run requires billing on (free tier covers our usage).
3. **A Gemini API key** in `.env` as `GOOGLE_API_KEY` (the deploy script picks it up automatically).

## Deploy

From the project root:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id ./infra/deploy.sh
```

Optional overrides:
```bash
GOOGLE_CLOUD_LOCATION=us-central1  \
GEMINI_PLANNER_MODEL=gemini-3.1-flash-lite \
GEMINI_WORKER_MODEL=gemini-3.1-flash-lite \
GOOGLE_CLOUD_PROJECT=your-project-id \
./infra/deploy.sh
```

The script:
1. Sets the active gcloud project
2. Enables Cloud Run, Cloud Build, Artifact Registry APIs
3. Builds + deploys Phoenix (`infra/phoenix/Dockerfile`)
4. Builds + deploys Dashboard (root `Dockerfile`) with Phoenix URL wired in
5. Prints both URLs

Total time: ~5-8 minutes on first deploy. Subsequent deploys are faster (Cloud Build caches layers).

## Seed demo data

After deploy, the Phoenix instance is empty. Seed it with realistic failures so the demo loop has data to chew on. Run from your **local** machine (the seeder calls the target agent which calls Gemini and emits traces to deployed Phoenix):

```bash
PHOENIX_BASE_URL=<phoenix-url-from-deploy> \
PHOENIX_COLLECTOR_ENDPOINT=<phoenix-url>/v1/traces \
uv run python -m scripts.seed_failures
```

Then open the Dashboard URL and click ▶ Run.

## Updating

To push code changes:
```bash
GOOGLE_CLOUD_PROJECT=your-project-id ./infra/deploy.sh
```
The script re-runs the deploy idempotently. New revisions take effect immediately.

## Tearing down

```bash
gcloud run services delete agent-sre-phoenix --region us-central1
gcloud run services delete agent-sre-dashboard --region us-central1
```

## Troubleshooting

**Build fails with "permission denied":** make sure the Cloud Build service account has `roles/run.admin` and `roles/iam.serviceAccountUser`. The deploy script enables the APIs but doesn't grant roles — gcloud usually grants them automatically on first deploy, but if not:
```bash
PROJECT_NUM=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member="serviceAccount:${PROJECT_NUM}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"
```

**Container starts but health check fails:** check Cloud Run logs:
```bash
gcloud run services logs read agent-sre-dashboard --region us-central1 --limit 50
```
Most common cause: a required env var is missing. The deploy script sets `GOOGLE_API_KEY`, `PHOENIX_BASE_URL`, etc. — verify they're set in the Cloud Run revision.

**Phoenix loses traces on restart:** Expected — Cloud Run filesystem is ephemeral. Re-seed with the script above. For persistence, mount Cloud SQL.
