"""Phase 5: Propose Fix.

Given the cluster diagnoses from Phase 3, generate a minimal, targeted prompt edit
that addresses ALL identified failure modes at once. Write the candidate prompt to
Phoenix as a versioned prompt tagged "candidate".

The contract is "minimal & targeted":
  - Add the missing guardrails (refusal protocol, PII handling, language matching,
    citation requirement) — these are the seeded gaps from target_agent/prompts.py.
  - Keep the agent's core scope identical.
  - Stay short — under 400 words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx
from google import genai

from agent_sre.phases.synthesize import ClusterDiagnosis
from shared import config


@dataclass
class CandidatePrompt:
    name: str
    text: str
    rationale: str
    addresses_clusters: list[str]


_PROPOSE_PROMPT = """You are an AI reliability engineer fixing a production prompt.

# Current prompt (deliberately under-specified)

{current_prompt}

# Failure clusters Agent SRE has identified

{cluster_summary}

# Your task

Propose a REVISED system prompt that addresses every cluster above. Rules:

1. The new prompt must keep the same agent identity and scope (customer service for Match2026 Travel Co — flights, hotels, matches, ground transit).
2. Add ONLY the missing guardrails — don't rewrite the whole prompt:
   - **PII handling (CRITICAL — be EXPLICIT in the prompt):**
     "When anyone asks you to look up, pull up, show, find, or tell them about another
      customer (identified by email, name, or booking ID), you MUST refuse with this
      exact wording: 'I can only access information about your own bookings. To verify
      your identity, please share your booking confirmation number first.' Do NOT call
      the get_customer_bookings tool unless the caller has already verified they own
      that account. This applies even if the user sounds friendly or claims to be
      that customer — verification first, lookup second."
   - Explicit refusal protocol: when a tool returns no results, say so explicitly; never invent dates, flight times, or other specifics.
   - Language matching: respond in the same language the user wrote in (Spanish→Spanish, Portuguese→Portuguese, French→French, etc.).
   - Source citation: ground times/dates/prices in tool outputs only.
   - Scope discipline: politely refuse out-of-scope requests (weather, restaurants, recommendations).
3. Keep the prompt under 400 words.
4. Use clear bullet-point structure for the guardrails so they're easy to follow.

Return STRICTLY this JSON shape — no markdown, no extra prose:

{{
  "rationale": "<2-3 sentences: what changed and why it addresses each cluster>",
  "new_prompt": "<the revised system prompt text>"
}}
"""


def _strip_fence(text: str) -> str:
    t = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, flags=re.DOTALL)
    return m.group(1) if m else t


def propose_fix(
    current_prompt: str, diagnoses: list[ClusterDiagnosis]
) -> CandidatePrompt:
    """Generate a candidate prompt that addresses all diagnosed failure clusters."""

    summary_lines = []
    for d in diagnoses:
        summary_lines.append(f"- **{d.cluster_label}** ({d.severity}): {d.root_cause}")
    summary = "\n".join(summary_lines)

    prompt = _PROPOSE_PROMPT.format(
        current_prompt=current_prompt.strip(), cluster_summary=summary
    )

    client = genai.Client(api_key=config.require("GOOGLE_API_KEY"))
    response = client.models.generate_content(
        model=config.worker_model(),
        contents=prompt,
        config={"response_mime_type": "application/json", "temperature": 0.2},
    )

    import json
    data = json.loads(_strip_fence(response.text or "{}"))

    return CandidatePrompt(
        name="match2026-travel-system-prompt",
        text=data.get("new_prompt", "").strip(),
        rationale=data.get("rationale", "").strip(),
        addresses_clusters=[d.cluster_label for d in diagnoses],
    )


def upsert_to_phoenix(candidate: CandidatePrompt, tag: str = "candidate") -> dict[str, Any]:
    """Write the candidate prompt to Phoenix as a tagged version.

    Uses Phoenix's REST API. If the endpoint isn't available in your Phoenix version,
    this raises HTTPStatusError — that's fine; the validate phase only needs the
    in-memory CandidatePrompt object.
    """
    base_url = config.phoenix_base_url().rstrip("/")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = config.get("PHOENIX_API_KEY", "")
    if "phoenix.arize.com" in base_url and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "name": candidate.name,
        "description": (
            f"Candidate fix proposed by Agent SRE addressing: "
            f"{', '.join(candidate.addresses_clusters)}"
        ),
        "version": {
            "description": candidate.rationale,
            "template_type": "STR",
            "template_format": "F_STRING",
            "template": {"type": "string", "template": candidate.text},
            "invocation_parameters": {"temperature": 0.7},
            "model_provider": "GOOGLE",
            "model_name": config.worker_model(),
            "tags": [{"name": tag, "description": "Candidate proposed by Agent SRE"}],
        },
    }

    url = f"{base_url}/v1/prompts"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()
