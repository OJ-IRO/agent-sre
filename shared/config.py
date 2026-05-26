"""Centralized config loading with lazy validation.

We don't validate at import time — that would break IDE imports and tooling. Instead,
each accessor validates when called, raising a clear error if a required env var is
missing.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def get(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def require(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(
            f"Required env var {name} is not set. See .env.example for the full list."
        )
    return val


def planner_model() -> str:
    # Default to 2.5-flash-lite: highest free-tier RPD of any current Gemini model.
    # Verified working as of 2026-05-25. Swap to gemini-3-flash-preview or
    # gemini-3.1-pro-preview when billing is on or for the final demo recording.
    return get("GEMINI_PLANNER_MODEL", "gemini-2.5-flash-lite")


def worker_model() -> str:
    return get("GEMINI_WORKER_MODEL", "gemini-2.5-flash-lite")


def phoenix_collector_endpoint() -> str:
    return get("PHOENIX_COLLECTOR_ENDPOINT", "https://app.phoenix.arize.com/v1/traces")


def phoenix_base_url() -> str:
    return get("PHOENIX_BASE_URL", "https://app.phoenix.arize.com")


def phoenix_project_name() -> str:
    return get("PHOENIX_PROJECT_NAME", "match2026-travel")


def phoenix_mcp_url() -> str:
    return get("PHOENIX_MCP_URL", "https://app.phoenix.arize.com/mcp")
