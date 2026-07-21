# Data dictionary

## Table: `sessions`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Session primary key |
| task_id | text | Task id (`simple_rt` or `tmb:SimpleRT`, …) |
| source | text | `simple_rt` \| `tmb_run` |
| status | text | `active` \| `complete` \| `incomplete` |
| device_info | text | JSON / UA string |
| referer | text | Browser referer (TMB submits) |
| client_score | float | Score from TMB form field `score` |
| raw_data_json | text | Full TMB `data` payload |
| raw_outcomes_json | text | Full TMB `outcomes` payload |
| created_at | timestamptz | Server create time |
| completed_at | timestamptz | Set on `/complete` or `/run` |

## Table: `trials`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Trial primary key |
| session_id | UUID | FK → sessions.id |
| trial_index | int | 0-based order in session |
| trial_type | text | `practice` \| `test` |
| stimulus_id | text | Stimulus label (`go`) |
| response | text | `space` \| `pointer` \| null |
| correct | bool | Response correctness |
| rt_ms | float | Reaction time milliseconds |
| flagged | bool | Per-trial QC flag |
| flag_reason | text | See SCORING.md |
| raw_json | text | Original TMB trial object when source=tmb_run |
| client_ts | timestamptz | Client ISO timestamp |
| created_at | timestamptz | Server insert time |

## Table: `summaries`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Summary primary key |
| session_id | UUID | FK → sessions.id (1:1) |
| n_test_trials | int | Test trial count |
| n_valid_trials | int | Unflagged test trials with RT |
| n_flagged_trials | int | Flagged test trials |
| mean_rt_ms | float | Mean RT of valid trials |
| median_rt_ms | float | Median RT of valid trials |
| sd_rt_ms | float | Sample SD of valid RTs |
| accuracy | float | 0–1 |
| score | float | 0–100 inverse-RT style score (see SCORING.md) |
| qc_flag_any | bool | Session-level QC |
| qc_notes | text | Machine-readable notes |
| created_at | timestamptz | Row time |

## CSV export

`GET /v1/sessions/{id}/export.csv` stacks:

1. One row per trial (`record_type=trial`)
2. One summary row (`record_type=summary`)

Researchers can filter by `record_type` for raw vs derived tables.
