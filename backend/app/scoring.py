from __future__ import annotations

import math
import statistics

from app.models import TrialRow

# Thresholds documented in SCORING.md
RT_TOO_FAST_MS = 100.0
RT_TOO_SLOW_MS = 2000.0
MIN_VALID_FRACTION = 0.7


def flag_trial(rt_ms: float | None, response: str | None) -> tuple[bool, str | None]:
    if response is None:
        return True, "no_response"
    if rt_ms is None:
        return True, "missing_rt"
    if rt_ms < RT_TOO_FAST_MS:
        return True, "rt_too_fast"
    if rt_ms > RT_TOO_SLOW_MS:
        return True, "rt_too_slow"
    return False, None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.fmean(values))


def _sd(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return float(statistics.stdev(values))


def compute_summary(trials: list[TrialRow]) -> dict:
    test = [t for t in trials if t.trial_type == "test"]
    flagged = [t for t in test if t.flagged]
    valid = [t for t in test if not t.flagged and t.rt_ms is not None]
    rts = [float(t.rt_ms) for t in valid if t.rt_ms is not None]

    mean_rt = _mean(rts)
    median_rt = _median(rts)
    sd_rt = _sd(rts)

    correct_vals = [t for t in valid if t.correct is not None]
    if correct_vals:
        accuracy = sum(1 for t in correct_vals if t.correct) / len(correct_vals)
    else:
        # Simple RT has no wrong answer when a response exists; treat valid as correct.
        accuracy = 1.0 if valid else None

    # score = min(100, 10000 / mean_rt_ms)
    score = None
    if mean_rt and mean_rt > 0:
        score = round(min(100.0, 10000.0 / mean_rt), 2)

    notes: list[str] = []
    qc_any = False
    if not test:
        notes.append("no_test_trials")
        qc_any = True
    else:
        valid_frac = len(valid) / len(test)
        if valid_frac < MIN_VALID_FRACTION:
            notes.append(f"low_valid_fraction:{valid_frac:.2f}")
            qc_any = True
        if flagged:
            notes.append(f"flagged_trials:{len(flagged)}")
            qc_any = True
        if mean_rt is not None and mean_rt < 150:
            notes.append("implausibly_fast_mean_rt")
            qc_any = True

    return {
        "n_test_trials": len(test),
        "n_valid_trials": len(valid),
        "n_flagged_trials": len(flagged),
        "mean_rt_ms": None if mean_rt is None else round(mean_rt, 2),
        "median_rt_ms": None if median_rt is None else round(median_rt, 2),
        "sd_rt_ms": None if sd_rt is None or math.isnan(sd_rt) else round(sd_rt, 2),
        "accuracy": None if accuracy is None else round(accuracy, 4),
        "score": score,
        "qc_flag_any": qc_any,
        "qc_notes": ";".join(notes) if notes else None,
    }
