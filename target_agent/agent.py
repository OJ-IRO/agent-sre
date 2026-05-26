"""Match2026 Travel Co — the target agent.

This is the agent that Agent SRE observes, diagnoses, and improves. It is deliberately
under-prompted so it produces a stream of legible production failures. See prompts.py
for the documented seeded flaws.
"""
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from shared import config
from shared.instrumentation import setup_tracing
from target_agent.prompts import ROOT_INSTRUCTION
from target_agent.tools import (
    get_customer_bookings,
    search_flights,
    search_hotels,
    search_matches,
)

setup_tracing(project_name=config.phoenix_project_name())


root_agent = LlmAgent(
    name="match2026_travel",
    model=config.worker_model(),
    description="Customer service concierge for Match2026 Travel Co.",
    instruction=ROOT_INSTRUCTION,
    tools=[
        FunctionTool(search_matches),
        FunctionTool(search_flights),
        FunctionTool(search_hotels),
        FunctionTool(get_customer_bookings),
    ],
)
