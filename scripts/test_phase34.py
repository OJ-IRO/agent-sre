"""Run Phase 1 → 2 → 3 → 4 end-to-end:
  Observe → Cluster → Diagnose → Synthesize Adversarial Evals → Push to Phoenix.

After running, open http://localhost:6006 → Datasets to see the auto-generated dataset.
"""
from agent_sre.phases.cluster import cluster_failures
from agent_sre.phases.observe import failure_candidates, observe
from agent_sre.phases.synthesize import diagnose_and_synthesize, push_to_phoenix_dataset


def main() -> None:
    # Phase 1
    spans = observe(limit=400)
    candidates = failure_candidates(spans)
    print(f"Phase 1: {len(spans)} spans -> {len(candidates)} candidates\n")
    if not candidates:
        print("No candidates — run scripts/seed_failures.py first.")
        return

    # Phase 2
    clusters = cluster_failures(candidates, max_traces=40)
    print(f"Phase 2: {len(clusters)} failure clusters\n")
    for i, c in enumerate(clusters, 1):
        print(f"  [{i}] {c.label}  ({c.severity}, n={c.count})")
    print()

    # Phase 3 + 4 — process the top 2 clusters by severity to keep this run snappy
    all_cases = []
    for c in clusters[:2]:
        print(f"\n{'='*70}\n[Phase 3+4] Diagnosing: {c.label}\n{'='*70}")
        diag = diagnose_and_synthesize(c, candidates)
        print(f"Root cause: {diag.root_cause}")
        print(f"Cited spans: {len(diag.cited_span_ids)}")
        print(f"Generated {len(diag.eval_cases)} adversarial eval cases:")
        for j, ec in enumerate(diag.eval_cases[:5], 1):
            print(f"  {j}. INPUT:    {ec.input[:90]}")
            print(f"     EXPECTED: {ec.expected_behavior[:90]}")
        if len(diag.eval_cases) > 5:
            print(f"  ... and {len(diag.eval_cases) - 5} more cases")
        all_cases.extend(diag.eval_cases)

    # Push everything to Phoenix
    print(f"\n{'='*70}\n[Phase 4 push] Writing {len(all_cases)} cases to Phoenix...")
    result = push_to_phoenix_dataset(all_cases)
    print(f"Phoenix response: {result}")
    print("\nOpen http://localhost:6006 -> Datasets to see the new dataset.")


if __name__ == "__main__":
    main()
