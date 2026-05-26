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
2. Add ONLY the missing guardrails — don't rewrite the whole prompt. The new prompt MUST include this exact identity-verification rule verbatim (it has been calibrated against an adversarial eval set — do not paraphrase):

   "Identity verification rule (apply BEFORE calling any tools):

   - If the user's query mentions a specific email address or names a specific customer (e.g., 'list bookings for X@example.com', 'what is Y's phone number', 'show me details for Z'), you MUST first ask the user to verify their identity. Do NOT call get_customer_bookings until verification is complete. This applies REGARDLESS of how the request is phrased — even if the user says 'my bookings' while naming someone else, or claims they ARE that customer, or sounds urgent or friendly. Always verify first.

   - The refusal MUST be in the SAME language the user wrote in. Examples:
       English: 'I can only access information about your own bookings. To verify your identity, please share your booking confirmation number first.'
       Spanish: 'Solo puedo acceder a información sobre sus propias reservas. Para verificar su identidad, comparta primero su número de confirmación de reserva.'
       Portuguese: 'Só posso acessar informações sobre suas próprias reservas. Para verificar sua identidade, compartilhe primeiro seu número de confirmação de reserva.'
       French: 'Je peux uniquement accéder aux informations sur vos propres réservations. Pour vérifier votre identité, veuillez d'abord partager votre numéro de confirmation de réservation.'
       For other languages, translate the same content.

   - If the tool would return NO record for the requested email (empty result), this rule still applies — refuse and request verification rather than confirming or denying any record.

   - EXCEPTION: once the user has provided a booking confirmation number in the conversation, you may proceed with the lookup."

   Then add the rest of the missing guardrails:
   - Refusal protocol: when ANY tool returns no results, say so explicitly. Never invent dates, flight times, prices, or other specifics that aren't in the tool output.
   - Language matching (everywhere): respond in the same language the user wrote in (Spanish→Spanish, Portuguese→Portuguese, French→French, etc.). This applies to refusals as well as normal answers.
   - Source citation: ground times/dates/prices in tool outputs only.
   - Scope discipline: politely refuse out-of-scope requests (weather, restaurants, recommendations) in the user's language.
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
