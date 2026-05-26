"""Run Phase 1 + Phase 2 end-to-end against real Phoenix traces."""
from agent_sre.phases.cluster import cluster_failures
from agent_sre.phases.observe import failure_candidates, observe


def main() -> None:
    spans = observe(limit=400)
    candidates = failure_candidates(spans)
    print(f"Phase 1: pulled {len(spans)} spans; {len(candidates)} candidates.\n")

    if not candidates:
        print("No candidates — run `uv run python -m scripts.seed_failures` first.")
        return

    print("Phase 2: clustering with Gemini...")
    clusters = cluster_failures(candidates, max_traces=40)

    print(f"\n{'=' * 70}")
    print(f"FOUND {len(clusters)} FAILURE CLUSTERS")
    print("=" * 70)
    for i, c in enumerate(clusters, 1):
        sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(c.severity, "⚪")
        print(f"\n[{i}] {sev_icon}  {c.label}  ({c.severity}, n={c.count})")
        print(f"    {c.description}")
        for inp in c.sample_inputs[:3]:
            preview = inp.replace("\n", " ").strip()[:100]
            print(f"      • {preview}")


if __name__ == "__main__":
    main()
