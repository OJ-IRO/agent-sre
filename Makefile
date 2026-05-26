.PHONY: install run-target run-sre spike deploy-target deploy-sre clean

# Install all deps via uv.
install:
	uv sync

# Start self-hosted Phoenix locally at http://localhost:6006. Run in a separate terminal.
serve-phoenix:
	uv run phoenix serve

# Run the target agent locally with ADK's dev web UI.
run-target:
	uv run adk web target_agent

# Run Agent SRE locally with ADK's dev web UI.
run-sre:
	uv run adk web agent_sre

# End-to-end proof of life: one query to target, verify Agent SRE can read traces via MCP.
spike:
	uv run python -m scripts.spike

# Start the judge-facing dashboard at http://localhost:8080
serve-dashboard:
	uv run uvicorn dashboard.server:app --host 0.0.0.0 --port 8080 --reload

# Deploy the target agent to Cloud Run.
deploy-target:
	adk deploy cloud_run \
		--project=$$GOOGLE_CLOUD_PROJECT \
		--region=$$GOOGLE_CLOUD_LOCATION \
		--service_name=match2026-travel \
		target_agent

# Deploy Agent SRE to Cloud Run.
deploy-sre:
	adk deploy cloud_run \
		--project=$$GOOGLE_CLOUD_PROJECT \
		--region=$$GOOGLE_CLOUD_LOCATION \
		--service_name=agent-sre \
		agent_sre

clean:
	rm -rf .venv __pycache__ .pytest_cache *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
