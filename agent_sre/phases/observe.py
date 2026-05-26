"""Phase 1: Observe.

Pull recent spans from the target project via Phoenix's REST API. Return a list of
SpanRecord objects shaped for downstream clustering.

Design notes:
  - We use Phoenix's REST API directly (httpx) rather than going through MCP for this
    phase. Reasoning: this phase needs to be FAST and DETERMINISTIC — it's just data
    extraction, no LLM judgment needed. MCP-mediated calls go through the LLM and
    are slower / less predictable. Later phases (synthesize evals, propose fix) DO
    use MCP via the LLM agent — those are where the "autonomous" demo lives.
  - The hackathon's MCP requirement is satisfied by Agent SRE's write-side phases
    (Synthesize Evals, Propose Fix, Ship), not by every read.

Tested against self-hosted Phoenix 16.x at http://localhost:6006.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from shared import config


@dataclass
class SpanRecord:
    """A normalized view of one span pulled from Phoenix."""

    span_id: str
    trace_id: str
    name: str
    start_time: str
    end_time: str | None
    status_code: str  # "OK", "ERROR", "UNSET"
    status_message: str | None
    input_value: str | None      # User prompt or tool input
    output_value: str | None     # Agent response or tool output
    latency_ms: float | None
    span_kind: str | None        # "LLM", "TOOL", "CHAIN", "AGENT", ...
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def is_failure_candidate(self) -> bool:
        """Heuristic: spans worth Agent SRE's attention.

        We're permissive here — we want Phase 2 (Cluster) to look at MOST spans
        and let Gemini decide which are real failures. Hard error spans are
        always candidates; otherwise we keep LLM-kind spans for content analysis.
        """
        if self.status_code == "ERROR":
            return True
        if self.span_kind in ("LLM", "AGENT"):
            return True
        return False


def _coerce_attr_string(value: Any) -> str | None:
    """Phoenix returns span attributes as dicts of various scalar types.
    Coerce to a string for downstream LLM processing."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        import json
        return json.dumps(value, default=str)[:4000]
    except Exception:
        return str(value)[:4000]


def _extract_clean_user_text(attrs: dict[str, Any]) -> str | None:
    """Walk the flat 'llm.input_messages.<i>.message.*' keys Phoenix produces to find
    the LAST user message's text content. Avoids the JSON envelope that lives in
    'input.value' (which contains the entire Gemini API request)."""
    indices: set[int] = set()
    for k in attrs:
        m = re.match(r"^llm\.input_messages\.(\d+)\.message\.role$", k)
        if m:
            indices.add(int(m.group(1)))
    for i in sorted(indices, reverse=True):
        if attrs.get(f"llm.input_messages.{i}.message.role") == "user":
            # Try the nested-contents form first (current ADK shape).
            text = attrs.get(
                f"llm.input_messages.{i}.message.contents.0.message_content.text"
            )
            if text:
                return str(text)
            text = attrs.get(f"llm.input_messages.{i}.message.content")
            if text:
                return str(text)
    return None


def _extract_clean_output_text(attrs: dict[str, Any]) -> str | None:
    """Pull the first output_message text. Same flattening rules as above."""
    text = attrs.get("llm.output_messages.0.message.contents.0.message_content.text")
    if text:
        return str(text)
    text = attrs.get("llm.output_messages.0.message.content")
    if text:
        return str(text)
    return None


def _parse_span(raw: dict[str, Any]) -> SpanRecord:
    """Map a raw Phoenix span dict into our SpanRecord shape.

    Phoenix's span payload structure has shifted across versions; we read defensively
    and tolerate missing fields rather than crashing.
    """
    attrs = raw.get("attributes") or {}

    # Phoenix flattens OpenInference attributes under semantic keys. Prefer the CLEAN
    # extracted user/agent text over the raw 'input.value' / 'output.value' fields,
    # which contain the full Gemini API JSON envelope and pollute downstream clustering.
    input_value = (
        _extract_clean_user_text(attrs)
        or attrs.get("input.value")
        or raw.get("input_value")
    )
    output_value = (
        _extract_clean_output_text(attrs)
        or attrs.get("output.value")
        or raw.get("output_value")
    )
    span_kind = (
        attrs.get("openinference.span.kind")
        or attrs.get("span.kind")
        or raw.get("span_kind")
    )

    status = raw.get("status") or {}
    if isinstance(status, dict):
        status_code = status.get("code") or status.get("status_code") or "UNSET"
        status_message = status.get("message")
    else:
        status_code = str(status)
        status_message = None

    # Latency: prefer explicit field, else compute from timestamps if both present.
    latency_ms = raw.get("latency_ms")
    if latency_ms is None and raw.get("start_time") and raw.get("end_time"):
        # Best-effort parse — Phoenix uses ISO 8601 strings.
        try:
            from datetime import datetime
            t0 = datetime.fromisoformat(raw["start_time"].replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(raw["end_time"].replace("Z", "+00:00"))
            latency_ms = (t1 - t0).total_seconds() * 1000
        except Exception:
            latency_ms = None

    return SpanRecord(
        span_id=raw.get("span_id") or raw.get("context", {}).get("span_id") or "",
        trace_id=raw.get("trace_id") or raw.get("context", {}).get("trace_id") or "",
        name=raw.get("name") or "(unnamed)",
        start_time=raw.get("start_time") or "",
        end_time=raw.get("end_time"),
        status_code=status_code,
        status_message=status_message,
        input_value=_coerce_attr_string(input_value),
        output_value=_coerce_attr_string(output_value),
        latency_ms=latency_ms,
        span_kind=span_kind,
        attributes=attrs,
    )


def observe(project_name: str | None = None, limit: int = 200) -> list[SpanRecord]:
    """Pull recent spans from a Phoenix project. Returns the candidate set for clustering.

    Args:
        project_name: Phoenix project. Defaults to PHOENIX_PROJECT_NAME from env.
        limit: max number of spans to fetch.

    Returns:
        List of SpanRecord, in reverse-chronological order. Empty list if the project
        has no spans yet.
    """
    project = project_name or config.phoenix_project_name()
    base_url = config.phoenix_base_url().rstrip("/")

    # Phoenix exposes a REST endpoint for listing spans per project. We pass auth
    # headers when talking to Phoenix Cloud; localhost has no auth.
    headers: dict[str, str] = {}
    api_key = config.get("PHOENIX_API_KEY", "")
    if "phoenix.arize.com" in base_url and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    url = f"{base_url}/v1/projects/{project}/spans"
    params = {"limit": str(limit)}

    with httpx.Client(timeout=30.0) as client:
        r = client.get(url, headers=headers, params=params)
        if r.status_code == 404:
            # Project doesn't exist yet — nothing to observe.
            return []
        r.raise_for_status()
        payload = r.json()

    # Phoenix returns either a list or {"data": [...]} depending on version.
    raw_spans = payload if isinstance(payload, list) else payload.get("data", [])
    return [_parse_span(s) for s in raw_spans]


def failure_candidates(spans: list[SpanRecord]) -> list[SpanRecord]:
    """Filter observed spans down to those worth diagnosing."""
    return [s for s in spans if s.is_failure_candidate]
