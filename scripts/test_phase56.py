"""Run Phase 1 → 6 end-to-end. The full demo loop:
Observe → Cluster → Diagnose → Synthesize Evals → Propose Fix → Validate.
"""
import asyncio

from agent_sre.phases.cluster import cluster_failures
from agent_sre.phases.observe import failure_candidates, observe
from agent_sre.phases.propose import propose_fix, upsert_to_phoenix
from agent_sre.phases.synthesize import diagnose_and_synthesize
from agent_sre.phases.validate import validate
from target_agent.prompts import ROOT_INSTRUCTION


async def main() -> None:
    spans = observe(limit=400)
    candidates = failure_candidates(spans)
    print(f"Phase 1: {len(spans)} spans -> {len(candidates)} candidates")

    clusters = cluster_failures(candidates, max_traces=40)
    print(f"Phase 2: {len(clusters)} clusters")
    for c in clusters:
        print(f"  - {c.label} ({c.severity}, n={c.count})")

    print(f"\nPhase 3+4: diagnosing top 2 clusters & synthesizing evals...")
    diagnoses = []
    all_cases = []
    for c in clusters[:2]:
        d = diagnose_and_synthesize(c, candidates)
        diagnoses.append(d)
        all_cases.extend(d.eval_cases)
        print(f"  - {c.label}: {len(d.eval_cases)} cases")

    print(f"\nPhase 5: proposing fix...")
    candidate = propose_fix(ROOT_INSTRUCTION, diagnoses)
    print(f"  Rationale: {candidate.rationale}")
    print(f"  New prompt ({len(candidate.text)} chars, addressing {len(candidate.addresses_clusters)} clusters):")
    print("  ---")
    for line in candidate.text.splitlines():
        print(f"  | {line}")
    print("  ---")
    try:
        result = upsert_to_phoenix(candidate)
        print(f"  Pushed to Phoenix prompts: {result.get('data', {}).get('id', '?')}")
    except Exception as e:
        print(f"  (Phoenix prompt push failed; continuing with in-memory candidate): {e}")

    print(f"\nPhase 6: validating against {len(all_cases)} eval cases (subsampling 6)...")
    print("(This takes a few minutes due to free-tier rate limits.)\n")
    val = await validate(all_cases, ROOT_INSTRUCTION, candidate.text, max_cases=8)

    print("\n" + "=" * 70)
    print(f"BEFORE: {val.original_score:.0%}  ({sum(1 for c in val.cases if c.original_passed)}/{len(val.cases)})")
    print(f"AFTER:  {val.candidate_score:.0%}  ({sum(1 for c in val.cases if c.candidate_passed)}/{len(val.cases)})")
    print(f"DELTA:  {val.delta:+.0%}")
    print("=" * 70)

    print("\nPer-case detail:")
    for r in val.cases:
        marker = "✗→✓" if (not r.original_passed and r.candidate_passed) else (
            "✓→✓" if r.candidate_passed else "✗→✗"
        )
        print(f"\n  {marker}  {r.case.input[:80]}")
        print(f"      expected:  {r.case.expected_behavior[:80]}")
        print(f"      original:  {r.original_output[:80]}")
        print(f"      candidate: {r.candidate_output[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
