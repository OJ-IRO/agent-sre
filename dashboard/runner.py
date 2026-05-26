"""Pipeline orchestrator for the dashboard.

Wraps the 8-phase Agent SRE loop as an async generator that yields SSE events.
The dashboard consumes these and renders progress live.
"""
from __future__ import annotations

import asyncio
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


async def run_pipeline(
    max_cases: int = 6, top_n_clusters: int = 2
) -> AsyncGenerator[dict[str, Any], None]:
    """Yield SSE events as the 8-phase loop executes against live Phoenix data."""
    try:
        yield {"type": "pipeline_start"}

        # ---- Phase 1 — Observe ----
        yield {"type": "phase_start", "phase": 1, "name": "Observe"}
        spans = await asyncio.to_thread(observe, limit=400)
        candidates = failure_candidates(spans)
        yield {
            "type": "phase_complete",
            "phase": 1,
            "summary": f"{len(candidates)} failure candidates from {len(spans)} spans",
            "metrics": {"spans": len(spans), "candidates": len(candidates)},
        }

        if not candidates:
            yield {
                "type": "pipeline_error",
                "message": "No failure candidates found. Run scripts/seed_failures.py first.",
            }
            return

        # ---- Phase 2 — Cluster ----
        yield {"type": "phase_start", "phase": 2, "name": "Cluster"}
        clusters = await asyncio.to_thread(cluster_failures, candidates, 40)
        for c in clusters:
            yield {
                "type": "cluster_found",
                "label": c.label,
                "severity": c.severity,
                "count": c.count,
                "description": c.description,
            }
        yield {
            "type": "phase_complete",
            "phase": 2,
            "summary": f"{len(clusters)} clusters identified",
            "metrics": {"clusters": len(clusters)},
        }

        # ---- Phase 3 + 4 — Diagnose + Synthesize ----
        yield {"type": "phase_start", "phase": 3, "name": "Diagnose"}
        yield {"type": "phase_start", "phase": 4, "name": "Synthesize evals"}
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
        yield {
            "type": "phase_complete",
            "phase": 3,
            "summary": f"{len(diagnoses)} clusters diagnosed",
            "metrics": {"diagnoses": len(diagnoses)},
        }
        yield {
            "type": "phase_complete",
            "phase": 4,
            "summary": f"{len(all_cases)} adversarial eval cases written",
            "metrics": {"eval_cases": len(all_cases)},
        }

        # ---- Phase 5 — Propose Fix ----
        yield {"type": "phase_start", "phase": 5, "name": "Propose Fix"}
        candidate = await asyncio.to_thread(propose_fix, ROOT_INSTRUCTION, diagnoses)
        yield {
            "type": "candidate_proposed",
            "rationale": candidate.rationale,
            "prompt": candidate.text,
            "prompt_length_chars": len(candidate.text),
            "addresses_clusters": candidate.addresses_clusters,
        }
        yield {
            "type": "phase_complete",
            "phase": 5,
            "summary": f"Candidate prompt drafted ({len(candidate.text)} chars)",
        }

        # ---- Phase 6 — Validate ----
        yield {"type": "phase_start", "phase": 6, "name": "Validate"}
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
        yield {
            "type": "phase_complete",
            "phase": 6,
            "summary": f"BEFORE: {val.original_score:.0%}  AFTER: {val.candidate_score:.0%}  DELTA: {val.delta:+.0%}",
            "metrics": {"before": val.original_score, "after": val.candidate_score, "delta": val.delta},
        }

        # ---- Phase 7 — Ship ----
        yield {"type": "phase_start", "phase": 7, "name": "Ship"}
        ship_result = await asyncio.to_thread(
            ship, ROOT_INSTRUCTION, candidate, diagnoses, val
        )
        yield {
            "type": "ship_decision",
            "shipped": ship_result.shipped,
            "reason": ship_result.reason,
            "postmortem_path": ship_result.postmortem_path,
        }
        if not ship_result.shipped:
            yield {
                "type": "phase_complete",
                "phase": 7,
                "summary": f"NOT SHIPPED: {ship_result.reason}",
            }
            yield {"type": "pipeline_complete", "shipped": False}
            return
        yield {
            "type": "phase_complete",
            "phase": 7,
            "summary": "Shipped. Postmortem written.",
        }

        # ---- Phase 8 — Drift Watch (single check) ----
        yield {"type": "phase_start", "phase": 8, "name": "Drift Watch"}
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
        yield {
            "type": "phase_complete",
            "phase": 8,
            "summary": (
                "REGRESSION DETECTED — would re-enter loop"
                if drift.regression_detected
                else f"Stable. Baseline {drift.baseline_score:.0%}, current {drift.current_score:.0%}"
            ),
        }

        yield {"type": "pipeline_complete", "shipped": True}

    except Exception as e:
        yield {
            "type": "pipeline_error",
            "message": str(e),
            "traceback": traceback.format_exc()[-2000:],
        }
