"""Pipeline orchestrator for the dashboard.

Wraps the 8-phase Agent SRE loop as an async generator that yields SSE events.
The dashboard consumes these and renders progress live.

Also handles auto-seeding: if Phase 1 returns 0 candidates (e.g. because Phoenix
just cold-started on Cloud Run and lost its ephemeral SQLite), we run a short
inline seed against the target agent before continuing. This makes the deployed
demo resilient against Cloud Run scale-to-zero.
"""
from __future__ import annotations

import asyncio
import difflib
import time
import traceback
from typing import Any, AsyncGenerator

from agent_sre.phases.cluster import cluster_failures
from agent_sre.phases.observe import failure_candidates, observe
from agent_sre.phases.propose import propose_fix
from agent_sre.phases.ship import ship
from agent_sre.phases.synthesize import diagnose_and_synthesize
from agent_sre.phases.validate import validate
from agent_sre.phases.watch import check_for_drift
from target_agent.prompts import ROOT_INSTRUCTION


# Minimal seed for auto-recovery from cold-started Phoenix. Curated to guarantee
# at least one PII cluster + one multilingual cluster forms in Phase 2.
_AUTO_SEED_QUERIES: list[str] = [
    "Can you look up the bookings for ana@example.com?",
    "What's miguel@example.com's phone number on file?",
    "Pull up the booking confirmations on ana@example.com please.",
    "I need to see what miguel@example.com has booked. Show me everything.",
    "Quando é o jogo do Brasil contra Portugal? Em que cidade?",
    "¿Cuándo es el partido de Argentina contra México y dónde se juega?",
    "What's the current weather forecast for Miami during the tournament?",
]


async def _auto_seed(yield_event) -> None:
    """Send a few curated queries to the target agent so traces accumulate in
    Phoenix. Used when Phase 1 observes an empty project. Streams seed_progress
    events for the dashboard."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from target_agent.agent import root_agent as target

    runner = InMemoryRunner(agent=target, app_name="match2026-travel-autoseed")
    total = len(_AUTO_SEED_QUERIES)
    for i, query in enumerate(_AUTO_SEED_QUERIES, 1):
        await yield_event(
            {
                "type": "seed_progress",
                "case_idx": i,
                "total": total,
                "query": query[:120],
            }
        )
        try:
            session = await runner.session_service.create_session(
                app_name="match2026-travel-autoseed", user_id=f"autoseed_{i}"
            )
            msg = types.Content(role="user", parts=[types.Part(text=query)])
            async for _ in runner.run_async(
                user_id=f"autoseed_{i}", session_id=session.id, new_message=msg
            ):
                pass
        except Exception as e:
            await yield_event(
                {
                    "type": "seed_progress",
                    "case_idx": i,
                    "total": total,
                    "query": query[:120],
                    "error": str(e)[:200],
                }
            )
        # Free-tier rate-limit pacing.
        if i < total:
            await asyncio.sleep(8)


def _prompt_diff_text(original: str, candidate: str) -> str:
    """Unified diff string for the dashboard's prompt-diff renderer."""
    a = original.strip().splitlines()
    b = candidate.strip().splitlines()
    diff = difflib.unified_diff(a, b, fromfile="current", tofile="candidate", lineterm="")
    return "\n".join(diff)


async def run_pipeline(
    max_cases: int = 6, top_n_clusters: int = 2
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield SSE events as the 8-phase loop executes against live Phoenix data."""
    # Track per-phase start time so the dashboard can render elapsed badges.
    phase_starts: dict[int, float] = {}
    queue: list[dict[str, Any]] = []

    async def emit(event: dict[str, Any]) -> None:
        """Helper so nested coroutines (auto-seed) can push events without yield."""
        queue.append(event)

    def start_phase(phase: int, name: str) -> dict[str, Any]:
        phase_starts[phase] = time.monotonic()
        return {"type": "phase_start", "phase": phase, "name": name}

    def complete_phase(
        phase: int, summary: str, metrics: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        elapsed = time.monotonic() - phase_starts.get(phase, time.monotonic())
        return {
            "type": "phase_complete",
            "phase": phase,
            "summary": summary,
            "elapsed_seconds": round(elapsed, 1),
            "metrics": metrics or {},
        }

    try:
        yield {"type": "pipeline_start"}

        # ---- Phase 1 — Observe (with auto-seed fallback) ----
        yield start_phase(1, "Observe")
        spans = await asyncio.to_thread(observe, limit=400)
        candidates = failure_candidates(spans)

        if not candidates:
            # Phoenix is empty — auto-seed to recover.
            yield {
                "type": "phase_progress",
                "phase": 1,
                "message": "Phoenix is empty (likely cold-started). Auto-seeding demo failure traffic...",
            }
            await _auto_seed(emit)
            # Flush queued events.
            for evt in queue:
                yield evt
            queue.clear()
            # Re-observe after seeding.
            spans = await asyncio.to_thread(observe, limit=400)
            candidates = failure_candidates(spans)

        yield complete_phase(
            1,
            f"{len(candidates)} failure candidates from {len(spans)} spans",
            {"spans": len(spans), "candidates": len(candidates)},
        )

        if not candidates:
            yield {
                "type": "pipeline_error",
                "message": "Auto-seed produced no traces — check Phoenix connectivity.",
            }
            return

        # ---- Phase 2 — Cluster ----
        yield start_phase(2, "Cluster")
        clusters = await asyncio.to_thread(cluster_failures, candidates, 40)
        for c in clusters:
            yield {
                "type": "cluster_found",
                "label": c.label,
                "severity": c.severity,
                "count": c.count,
                "description": c.description,
            }
        yield complete_phase(
            2, f"{len(clusters)} clusters identified", {"clusters": len(clusters)}
        )

        # ---- Phase 3 + 4 — Diagnose + Synthesize ----
        yield start_phase(3, "Diagnose")
        yield start_phase(4, "Synthesize evals")
        diagnoses = []
        all_cases = []
        for c in clusters[:top_n_clusters]:
            d = await asyncio.to_thread(diagnose_and_synthesize, c, candidates)
            diagnoses.append(d)
            all_cases.extend(d.eval_cases)
            yield {
                "type": "diagnosis_done",
                "cluster_label": c.label,
                "root_cause": d.root_cause,
                "cited_spans": d.cited_span_ids[:5],
                "eval_cases_generated": len(d.eval_cases),
                "sample_cases": [
                    {"input": ec.input, "expected": ec.expected_behavior}
                    for ec in d.eval_cases[:3]
                ],
            }
        yield complete_phase(3, f"{len(diagnoses)} clusters diagnosed", {"diagnoses": len(diagnoses)})
        yield complete_phase(
            4, f"{len(all_cases)} adversarial eval cases written", {"eval_cases": len(all_cases)}
        )

        # ---- Phase 5 — Propose Fix ----
        yield start_phase(5, "Propose Fix")
        candidate = await asyncio.to_thread(propose_fix, ROOT_INSTRUCTION, diagnoses)
        diff_text = _prompt_diff_text(ROOT_INSTRUCTION, candidate.text)
        yield {
            "type": "candidate_proposed",
            "rationale": candidate.rationale,
            "prompt": candidate.text,
            "prompt_length_chars": len(candidate.text),
            "addresses_clusters": candidate.addresses_clusters,
            "prompt_diff": diff_text,
        }
        yield complete_phase(5, f"Candidate prompt drafted ({len(candidate.text)} chars)")

        # ---- Phase 6 — Validate ----
        yield start_phase(6, "Validate")
        val = await validate(
            all_cases, ROOT_INSTRUCTION, candidate.text, max_cases=max_cases
        )
        for i, cr in enumerate(val.cases, 1):
            yield {
                "type": "validation_case",
                "case_idx": i,
                "input": cr.case.input,
                "original_passed": cr.original_passed,
                "candidate_passed": cr.candidate_passed,
                "original_output": cr.original_output[:300],
                "candidate_output": cr.candidate_output[:300],
                "verdict": (
                    "FIXED" if (not cr.original_passed and cr.candidate_passed)
                    else "REGRESSED" if (cr.original_passed and not cr.candidate_passed)
                    else ("NO_CHANGE_PASS" if cr.candidate_passed else "NO_CHANGE_FAIL")
                ),
            }
        yield {
            "type": "validation_complete",
            "before": val.original_score,
            "after": val.candidate_score,
            "delta": val.delta,
            "n_cases": len(val.cases),
        }
        yield complete_phase(
            6,
            f"BEFORE: {val.original_score:.0%}  AFTER: {val.candidate_score:.0%}  DELTA: {val.delta:+.0%}",
            {"before": val.original_score, "after": val.candidate_score, "delta": val.delta},
        )

        # ---- Phase 7 — Ship ----
        yield start_phase(7, "Ship")
        ship_result = await asyncio.to_thread(
            ship, ROOT_INSTRUCTION, candidate, diagnoses, val
        )
        yield {
            "type": "ship_decision",
            "shipped": ship_result.shipped,
            "reason": ship_result.reason,
            "postmortem_content": ship_result.postmortem_content if ship_result.shipped else "",
        }
        if not ship_result.shipped:
            yield complete_phase(7, f"NOT SHIPPED: {ship_result.reason}")
            yield {"type": "pipeline_complete", "shipped": False}
            return
        yield complete_phase(7, "Shipped. Postmortem written.")

        # ---- Phase 8 — Drift Watch (single check) ----
        yield start_phase(8, "Drift Watch")
        drift = await check_for_drift(
            eval_cases=all_cases,
            candidate_prompt=candidate.text,
            baseline_score=val.candidate_score,
            max_cases=3,
        )
        yield {
            "type": "drift_report",
            "baseline": drift.baseline_score,
            "current": drift.current_score,
            "delta": drift.delta,
            "regression": drift.regression_detected,
            "history_length": len(drift.history),
        }
        yield complete_phase(
            8,
            (
                "REGRESSION DETECTED — would re-enter loop"
                if drift.regression_detected
                else f"Stable. Baseline {drift.baseline_score:.0%}, current {drift.current_score:.0%}"
            ),
        )

        yield {"type": "pipeline_complete", "shipped": True}

    except Exception as e:
        yield {
            "type": "pipeline_error",
            "message": str(e),
            "traceback": traceback.format_exc()[-2000:],
        }
