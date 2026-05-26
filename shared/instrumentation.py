"""Phoenix tracing setup. Both the target agent and Agent SRE call setup_tracing()
once at process startup. Idempotent — safe to call multiple times.

Supports two modes:
  - Self-hosted Phoenix (localhost): no auth headers
  - Phoenix Cloud: Bearer auth headers required

The mode is selected by inspecting PHOENIX_BASE_URL.
"""
from phoenix.otel import register

from shared import config

_provider = None


def setup_tracing(project_name: str | None = None):
    """Initialize Phoenix OTel tracing with OpenInference auto-instrumentation."""
    global _provider
    if _provider is not None:
        return _provider

    endpoint = config.phoenix_collector_endpoint()
    name = project_name or config.phoenix_project_name()

    # Send auth headers only when talking to Phoenix Cloud. Self-hosted local
    # Phoenix has no auth by default.
    headers: dict[str, str] = {}
    if "phoenix.arize.com" in endpoint:
        api_key = config.require("PHOENIX_API_KEY")
        headers = {"Authorization": f"Bearer {api_key}"}

    _provider = register(
        project_name=name,
        endpoint=endpoint,
        headers=headers or None,
        batch=False,           # ship traces immediately so the demo loop is visible
        auto_instrument=True,  # OpenInference instruments ADK + GenAI calls
        verbose=False,
    )
    return _provider
