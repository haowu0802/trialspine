# Scoring and QC (`simple_rt`)

How the built-in reaction-time task is scored. Code lives in `backend/app/scoring.py`. Thresholds here are for the demo — not norms from TestMyBrain or clinical batteries.

Open TMB pages submit through `POST /run` with whatever `score` and `outcomes` the browser sends. Those are stored as-is; this file does not apply to them.

## Trials

Green **GO**, then Space or tap. Each row in `trials` has `rt_ms` (onset to response). Practice trials are stored but skipped when computing summaries.

## Per-trial flags

Each **test** trial can be marked `flagged` before stats run:

| what happened | `flag_reason` |
|---------------|---------------|
| no keypress | `no_response` |
| response but no RT | `missing_rt` |
| RT &lt; 100 ms | `rt_too_fast` |
| RT &gt; 2000 ms | `rt_too_slow` |

Summaries use only unflagged test trials that have a numeric `rt_ms`.

## Summary fields

All counts and RT stats are over **test** trials only.

| field | meaning |
|-------|---------|
| `n_test_trials` | test trial count |
| `n_valid_trials` | unflagged test trials with RT |
| `n_flagged_trials` | flagged test trials |
| `mean_rt_ms`, `median_rt_ms`, `sd_rt_ms` | RT over valid trials (`sd_rt_ms` needs ≥2 trials) |
| `accuracy` | share correct on valid trials; for simple RT, a response is treated as correct |
| `score` | `min(100, 10000 / mean_rt_ms)`, 2 decimals |

## Session QC

`qc_flag_any` turns on when the session looks unreliable for analysis:

- no test trials at all
- valid trials are less than 70% of test trials → `low_valid_fraction:0.xx` in `qc_notes`
- any flagged test trial → `flagged_trials:N`
- mean RT on valid trials &lt; 150 ms → `implausibly_fast_mean_rt`

`qc_notes` is semicolon-separated tokens.

## Sanity-check from CSV

`GET /v1/sessions/{id}/export.csv` → keep `record_type = trial` and `trial_type = test` → reapply flags and recompute. If that disagrees with `summaries`, trust the trial rows.
