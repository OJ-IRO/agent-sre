.PHONY: install run-target run-sre run-pipeline serve-dashboard serve-phoenix deploy clean

# Install all deps via uv.
install:
	uv sync

# Start a self-hosted Phoenix instance locally at http://localhost:6006.
# Run this in one terminal, then run other commands in another.
serve-phoenix:
	uv run phoenix serve

# Run the target agent locally with ADK's dev web UI.
run-target:
	uv run adk web target_agent

# Run Agent SRE locally with ADK's dev web UI.
run-sre:
	uv run adk web agent_sre

# Seed the target agent with demo failure traffic. Phoenix must be running.
seed:
	uv run python -m scripts.seed_failures

# Run the complete 8-phase autonomous loop end-to-end (terminal output).
run-pipeline:
	uv run python -m scripts.run_pipeline

# Start the judge-facing dashboard at http://localhost:8080.
serve-dashboard:
	uv run uvicorn dashboard.server:app --host 0.0.0.0 --port 8080 --reload

# Deploy Phoenix + Dashboard to Cloud Run. Requires GOOGLE_CLOUD_PROJECT.
deploy:
	bash ./infra/deploy.sh

clean:
	rm -rf .venv __pycache__ .pytest_cache *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
