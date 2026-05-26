"""Agent SRE — the autonomous reliability engineer.

Built with Google ADK. Connects to Phoenix MCP via HTTP transport. Starts as a
single-agent definition; will expand to a planner/worker hierarchy as we implement
the 8 phases.
"""
from google.adk.agents import LlmAgent

from shared import config
from shared.instrumentation import setup_tracing
from agent_sre.mcp_setup import phoenix_toolset
from agent_sre.prompts import ROOT_INSTRUCTION

setup_tracing(project_name="agent-sre-self")


root_agent = LlmAgent(
    name="agent_sre",
    model=config.planner_model(),
    description="Autonomous reliability engineer for AI agents in production.",
    instruction=ROOT_INSTRUCTION,
    tools=[phoenix_toolset()],
)
