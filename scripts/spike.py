"""End-to-end proof of life.

Step 1: Send one query to the target agent (Match2026 Travel Co). A trace lands in Phoenix.
Step 2: Spin up Agent SRE. Ask it to list traces from the target project via Phoenix MCP.
Step 3: Print what it found.

If all three steps succeed, the integration is verified end-to-end and we can start
implementing the 8-phase loop in earnest.
"""
import asyncio

from google.adk.runners import InMemoryRunner
from google.genai import types


async def step1_target_query():
    """Send one query to the target agent. Trace appears in Phoenix shortly."""
    from target_agent.agent import root_agent as target

    runner = InMemoryRunner(agent=target, app_name="match2026-travel")
    session = await runner.session_service.create_session(
        app_name="match2026-travel", user_id="spike_user"
    )

    msg = types.Content(
        role="user",
        parts=[types.Part(text="When is Argentina vs Mexico?")],
    )

    print("\n[STEP 1] Sending query to target agent...")
    print("  Q: When is Argentina vs Mexico?")
    async for event in runner.run_async(
        user_id="spike_user", session_id=session.id, new_message=msg
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"  A: {part.text}")


async def step2_sre_observes():
    """Run Agent SRE and ask it to list recent traces from the target project."""
    from agent_sre.agent import root_agent as sre

    runner = InMemoryRunner(agent=sre, app_name="agent-sre")
    session = await runner.session_service.create_session(
        app_name="agent-sre", user_id="spike_user"
    )

    msg = types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    "Call the list-projects tool to list all Phoenix projects. "
                    "Just show me the project names so I can verify the Phoenix MCP "
                    "connection works."
                )
            )
        ],
    )

    print("\n[STEP 2] Running Agent SRE to verify Phoenix MCP connection...")
    async for event in runner.run_async(
        user_id="spike_user", session_id=session.id, new_message=msg
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"  SRE: {part.text}")


async def main():
    await step1_target_query()
    print("\n--- Waiting 5 seconds for the trace to land in Phoenix ---")
    await asyncio.sleep(5)
    await step2_sre_observes()
    print(
        "\n[DONE] If you saw output above AND the trace shows up in your Phoenix "
        "dashboard at app.phoenix.arize.com, the integration is wired correctly."
    )


if __name__ == "__main__":
    asyncio.run(main())
