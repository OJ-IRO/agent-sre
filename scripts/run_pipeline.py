"""Run the complete 8-phase Agent SRE loop end-to-end.

  Observe → Cluster → Diagnose → Synthesize → Propose → Validate → Ship → Drift
"""
import asyncio

from agent_sre.phases.cluster import cluster_failures
from agent_sre.phases.observe import failure_candidates, observe
from agent_sre.phases.propose import propose_fix
from agent_sre.phases.ship import ship
from agent_sre.phases.synthesize import diagnose_and_synthesize
from agent_sre.phases.validate import validate
from agent_sre.phases.watch import check_for_drift
from target_agent.prompts import ROOT_INSTRUCTION


async def main() -> None:
    print("[1/8] Observe...")
    spans = observe(limit=400)
    candidates = failure_candidates(spans)
    print(f"      {len(spans)} spans -> {len(candidates)} candidates")

    print("\n[2/8] Cluster...")
    clusters = cluster_failures(candidates, max_traces=40)
    for c in clusters:
        print(f"      - {c.label} ({c.severity}, n={c.count})")

    print("\n[3/8 + 4/8] Diagnose & Synthesize evals for top 2 clusters...")
    diagnoses = []
    all_cases = []
    for c in clusters[:2]:
        d = diagnose_and_synthesize(c, candidates)
        diagnoses.append(d)
        all_cases.extend(d.eval_cases)
        print(f"      - {c.label}: {len(d.eval_cases)} adversarial cases")

    print("\n[5/8] Propose Fix...")
    candidate = propose_fix(ROOT_INSTRUCTION, diagnoses)
    print(f"      candidate prompt: {len(candidate.text)} chars")

    print("\n[6/8] Validate...")
    val = await validate(all_cases, ROOT_INSTRUCTION, candidate.text, max_cases=8)
    print(f"      BEFORE: {val.original_score:.0%}  AFTER: {val.candidate_score:.0%}  DELTA: {val.delta:+.0%}")

    print("\n[7/8] Ship...")
    ship_result = ship(ROOT_INSTRUCTION, candidate, diagnoses, val)
    if ship_result.shipped:
        print(f"      ✓ shipped. Postmortem: {ship_result.postmortem_path}")
        if ship_result.phoenix_response.get("warning"):
            print(f"      (Phoenix prompt tag: {ship_result.phoenix_response['warning']})")
        elif ship_result.phoenix_response:
            print(f"      Phoenix prompt tagged production: {ship_result.phoenix_response}")
    else:
        print(f"      ✗ not shipped. Reason: {ship_result.reason}")
        return

    print("\n[8/8] Drift Watch (single check)...")
    drift = await check_for_drift(
        eval_cases=all_cases,
        candidate_prompt=candidate.text,
        baseline_score=val.candidate_score,
        max_cases=4,
    )
    state = "REGRESSION DETECTED — re-entering loop" if drift.regression_detected else "stable"
    print(f"      baseline {drift.baseline_score:.0%} -> current {drift.current_score:.0%} ({drift.delta:+.0%})  [{state}]")
    print(f"      history length: {len(drift.history)}")

    print("\n" + "=" * 70)
    print("FULL LOOP COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
