"""Phase 8: Watch for drift.

Once a fix is shipped, Agent SRE keeps an eye on it. On a periodic schedule (Cloud
Scheduler in production; a sleep loop in dev), it re-runs validation against the
adversarial eval set and compares the score against the post-ship baseline. If the
score has degraded by more than a threshold, it re-enters the loop from Phase 1.

This is what makes Agent SRE "never sleep" — the final beat in the demo video.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_sre.phases.synthesize import EvalCase
from agent_sre.phases.validate import ValidationResult, validate


@dataclass
class DriftCheckpoint:
    timestamp: str
    score: float
    sample_size: int


@dataclass
class DriftReport:
    baseline_score: float
    current_score: float
    delta: float
    regression_detected: bool
    threshold: float
    history: list[DriftCheckpoint] = field(default_factory=list)


_HISTORY_PATH = "ship_artifacts/drift_history.jsonl"


def _load_history() -> list[DriftCheckpoint]:
    if not os.path.exists(_HISTORY_PATH):
        return []
    out: list[DriftCheckpoint] = []
    with open(_HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                out.append(
                    DriftCheckpoint(
                        timestamp=d["timestamp"],
                        score=d["score"],
                        sample_size=d["sample_size"],
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue
    return out


def _append_history(checkpoint: DriftCheckpoint) -> None:
    os.makedirs(os.path.dirname(_HISTORY_PATH), exist_ok=True)
    with open(_HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "timestamp": checkpoint.timestamp,
                    "score": checkpoint.score,
                    "sample_size": checkpoint.sample_size,
                }
            )
            + "\n"
        )


async def check_for_drift(
    eval_cases: list[EvalCase],
    candidate_prompt: str,
    baseline_score: float,
    regression_threshold: float = 0.10,
    max_cases: int = 5,
) -> DriftReport:
    """Run one drift check: re-validate the production prompt against the eval set.

    A drift is flagged if `current_score < baseline_score - regression_threshold`.
    Each call appends a checkpoint to the history file so we have a time series.

    Args:
        eval_cases: the adversarial dataset from Phase 4.
        candidate_prompt: the prompt currently in production (post-ship).
        baseline_score: the score this prompt achieved at ship time.
        regression_threshold: how big a drop counts as a regression.
        max_cases: subsample to keep drift checks cheap.

    Returns:
        DriftReport with current_score, delta, and the regression flag.
    """
    # Re-validate by running the candidate against itself — i.e., run validation
    # but with the candidate as "original". Score delta within validation will be 0;
    # we only care about candidate score here.
    val_result: ValidationResult = await validate(
        eval_cases,
        original_prompt=candidate_prompt,  # placeholder, ignored
        candidate_prompt=candidate_prompt,
        max_cases=max_cases,
    )

    current_score = val_result.candidate_score
    delta = current_score - baseline_score
    timestamp = datetime.now(timezone.utc).isoformat()

    checkpoint = DriftCheckpoint(
        timestamp=timestamp,
        score=current_score,
        sample_size=len(val_result.cases),
    )
    _append_history(checkpoint)

    return DriftReport(
        baseline_score=baseline_score,
        current_score=current_score,
        delta=delta,
        regression_detected=(delta < -regression_threshold),
        threshold=regression_threshold,
        history=_load_history(),
    )


async def watch_forever(
    eval_cases: list[EvalCase],
    candidate_prompt: str,
    baseline_score: float,
    interval_seconds: int = 3600,
    regression_threshold: float = 0.10,
    on_regression=None,
) -> None:
    """Production-style watch loop. Sleeps between checks; in real prod this is
    a Cloud Scheduler hook. For dev/demo, just run it in a thread or coroutine.

    Args:
        on_regression: optional callable invoked with the DriftReport when a
            regression fires. The orchestrator should re-enter the 8-phase loop.
    """
    while True:
        report = await check_for_drift(
            eval_cases, candidate_prompt, baseline_score, regression_threshold
        )
        if report.regression_detected and on_regression is not None:
            on_regression(report)
        await asyncio.sleep(interval_seconds)
