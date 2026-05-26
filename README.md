[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

# Agent SRE

**The first autonomous Site Reliability Engineer for AI agents in production.**

Agent SRE observes production traces from a deployed AI agent (via Arize Phoenix), clusters real failure modes, synthesizes adversarial evaluations from those failures, proposes prompt fixes, validates them via experiments, and ships PRs — autonomously, on a loop.

Built for the [Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com/) — **Arize partner track**.

> **Live demo:** https://agent-sre-dashboard-qnre34navq-uc.a.run.app
> Click ▶ Run to watch the 8-phase autonomous loop process real failure traces, generate adversarial evals, propose a fix, validate the delta, and ship — in real time.

---

## Why this exists

Every team running an LLM in production has the same problem: agents fail in ways nobody anticipated. Today, humans page through traces, hand-write evals, and iterate prompts by hand. Agent SRE does that loop autonomously — and it never sleeps.

## What it does (the 8-phase loop)

1. **Observe** — pull recent spans via Phoenix, filter to failure candidates
2. **Cluster** — Gemini groups failures into root-cause patterns
3. **Diagnose** — form hypotheses with cited span IDs
4. **Synthesize evals** — autonomously generate adversarial test cases, write them to a Phoenix dataset
5. **Propose fix** — draft a targeted prompt revision
6. **Validate** — run candidate vs. original against the adversarial set, score via Gemini-as-judge
7. **Ship** — if scores improved meaningfully, tag the prompt and write a postmortem PR (refuses to ship regressions)
8. **Watch for drift** — re-run regression evals on schedule, re-enter the loop if scores degrade

See [`examples/example-postmortem.md`](examples/example-postmortem.md) for an actual autonomous-generated postmortem from one run.

## Architecture

Two agents in the system:

1. **Match2026 Travel Co** ([`target_agent/`](target_agent/)) — the *target* agent being observed and improved. Built with Google ADK + Gemini, instrumented with OpenInference. Deliberately under-prompted so it produces legible production failures (PII leaks, hallucinated dates, multilingual drift) that Agent SRE can find and fix.
2. **Agent SRE** ([`agent_sre/`](agent_sre/)) — the *autonomous reliability engineer*. Each phase lives as its own module in [`agent_sre/phases/`](agent_sre/phases/). Reads from Phoenix, writes back to Phoenix via the Phoenix MCP server.

The [`dashboard/`](dashboard/) is a FastAPI + Server-Sent Events service that exposes the pipeline as a live Mission-Control-style UI.

## Stack

- **Agent runtime:** [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit) — code-owned, Cloud Run-deployable
- **LLMs:** Gemini 3.1 Flash Lite (planner + worker + LLM-as-judge — all Google models per hackathon rules)
- **Observability + MCP:** [Arize Phoenix](https://phoenix.arize.com/) + [`@arizeai/phoenix-mcp`](https://github.com/Arize-ai/phoenix/tree/main/js/packages/phoenix-mcp)
- **Hosting:** Cloud Run (two services), Cloud Build
- **Dashboard:** FastAPI + SSE + Tailwind (CDN)

## Quickstart (local)

```bash
# 1. Install deps
uv sync

# 2. Set up .env (copy template and fill in)
cp .env.example .env
# Edit .env: set GOOGLE_API_KEY (from https://aistudio.google.com/apikey)

# 3. Start a local Phoenix instance (in one terminal)
make serve-phoenix

# 4. Seed it with demo failure traffic (in another terminal)
make seed

# 5. EITHER run the pipeline in your terminal:
make run-pipeline

# OR serve the dashboard and run it interactively at http://localhost:8080:
make serve-dashboard
```

## Deploy to Cloud Run

```bash
GOOGLE_CLOUD_PROJECT=your-project-id make deploy
```

Deploys two Cloud Run services (Phoenix + Dashboard). See [`infra/README.md`](infra/README.md) for details and troubleshooting.

## Project structure

```
.
├── target_agent/         # Match2026 Travel Co — the demo target
├── agent_sre/            # Agent SRE itself
│   ├── phases/           # The 8 phase modules
│   ├── agent.py          # ADK LlmAgent with Phoenix MCP attached
│   └── mcp_setup.py      # Phoenix MCP toolset (stdio transport)
├── dashboard/            # FastAPI + SSE judge-facing UI
├── shared/               # Phoenix instrumentation, config
├── scripts/              # Operational commands (seed, run_pipeline)
├── infra/                # Cloud Run Dockerfiles + deploy.sh
├── examples/             # Sample autonomous outputs
├── Dockerfile            # Dashboard service image
├── Makefile              # Dev commands
└── LICENSE               # Apache-2.0
```

## License

Apache 2.0 — see [LICENSE](LICENSE).
