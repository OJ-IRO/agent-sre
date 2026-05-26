"""Manually exercise Phase 1 (Observe).

Run AFTER seed_failures.py has populated the Phoenix project with traces.
"""
from agent_sre.phases.observe import failure_candidates, observe


def main() -> None:
    spans = observe(limit=200)
    print(f"Pulled {len(spans)} total spans from Phoenix.")

    if not spans:
        print("No spans found. Run `uv run python -m scripts.seed_failures` first.")
        return

    failures = failure_candidates(spans)
    print(f"  {len(failures)} flagged as failure candidates for downstream clustering.\n")

    # Print a compact summary of the first 10
    for s in failures[:10]:
        latency = f"{s.latency_ms:.0f}ms" if s.latency_ms else "?ms"
        input_preview = (s.input_value or "")[:80].replace("\n", " ")
        print(f"  [{s.span_kind or '?':<6}] {s.name:<30} {s.status_code:<8} {latency:>8}  | {input_preview}")

    if len(failures) > 10:
        print(f"  ... and {len(failures) - 10} more")


if __name__ == "__main__":
    main()
