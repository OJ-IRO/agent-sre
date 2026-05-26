"""Phoenix MCP connection for Agent SRE.

Uses the stdio transport via `npx @arizeai/phoenix-mcp` — the canonical pattern
from Arize's starter repo. Works with both self-hosted Phoenix (localhost) and
Phoenix Cloud (with API key).
"""
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp.client.stdio import StdioServerParameters

from shared import config


def phoenix_toolset() -> McpToolset:
    """Build the Phoenix MCP toolset, wired to our Phoenix instance via stdio."""
    base_url = config.phoenix_base_url()
    api_key = config.get("PHOENIX_API_KEY", "")

    # Pin a known-good phoenix-mcp version. v4.0.13 (current "latest" as of May 2026)
    # ships with a broken openapi-fetch import path. v2.3.7 is the last stable release
    # before that regression — upgrade once upstream is fixed.
    args = [
        "-y",
        "@arizeai/phoenix-mcp@2.3.7",
        "--baseUrl",
        base_url,
    ]
    # Pass --apiKey only when talking to Phoenix Cloud; local Phoenix has no auth.
    if "phoenix.arize.com" in base_url and api_key and api_key != "local-dev-no-auth":
        args.extend(["--apiKey", api_key])

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command="npx", args=args)
        )
    )
