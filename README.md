[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

# Agent SRE

**The first autonomous Site Reliability Engineer for AI agents in production.**

Agent SRE observes production traces from a deployed AI agent (via Arize Phoenix), clusters real failure modes, synthesizes adversarial evaluations from those failures, proposes prompt fixes, validates them via experiments, and ships PRs — autonomously, on a loop.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com/) — Arize partner track.

## Why this exists

Every team running an LLM in production has the same problem: agents fail in ways nobody anticipated. Today, humans page through traces, hand-write evals, and iterate prompts. Agent SRE does that loop autonomously — and it never sleeps.

## Stack

- **Agent runtime:** [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit) — code-owned, deployable to Cloud Run
- **LLMs:** Gemini 3.1 Pro Preview (planner) + Gemini 3 Flash (worker, eval judge)
- **Observability + MCP:** [Arize Phoenix](https://phoenix.arize.com/) + [Phoenix MCP server](https://github.com/Arize-ai/phoenix/tree/main/js/packages/phoenix-mcp)
- **Infrastructure:** Cloud Run, Cloud SQL, Cloud Scheduler, Secret Manager, Vertex AI Embeddings
- **Demo target:** Match2026 Travel Co — a fictional multilingual travel concierge for the 2026 tournament, deliberately seeded with legible failure modes

## Architecture

Two agents in this submission:

1. **Match2026 Travel Co** (`target_agent/`) — the *target* agent being observed and improved. Built with ADK + Gemini, instrumented with OpenInference, deliberately under-prompted so it produces multilingual breakage, hallucinated dates, and PII leaks.
2. **Agent SRE** (`agent_sre/`) — the *autonomous reliability engineer*. Built with ADK, dual-model (Pro for planning, Flash for synthesis), connects to Phoenix via MCP, runs on a Cloud Scheduler loop.

### The 8-phase loop

1. **Observe** — pull recent traces via Phoenix MCP, filter to failures
2. **Cluster** — group failures into root-cause patterns
3. **Diagnose** — form hypotheses citing specific trace IDs
4. **Synthesize evals** — autonomously generate adversarial test cases, write them to a Phoenix dataset
5. **Propose fix** — draft a prompt edit, upsert it as a candidate prompt version
6. **Validate** — run candidate against the adversarial dataset, score via LLM-as-judge (Gemini)
7. **Ship** — if scores improved, promote prompt to production and draft a postmortem PR
8. **Watch for drift** — re-run regression evals, re-enter the loop if scores degrade

## Quickstart

```bash
cp .env.example .env
# Fill in PHOENIX_API_KEY, GOOGLE_API_KEY, GOOGLE_CLOUD_PROJECT
uv sync
make spike  # end-to-end proof of life
```

## Project structure

```
.
├── target_agent/      # Match2026 Travel Co (the target, deliberately flawed)
├── agent_sre/         # The autonomous reliability engineer
├── shared/            # Phoenix instrumentation, config
├── scripts/           # spike, smoke-tests, utilities
├── infra/             # gcloud deployment scripts
├── pyproject.toml
├── Makefile
└── LICENSE            # Apache-2.0
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
