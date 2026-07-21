from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    task_id: str = "simple_rt"
    device_info: str | None = None
    n_trials: int = Field(default=10, ge=1, le=60)


class SessionOut(BaseModel):
    id: uuid.UUID
    task_id: str
    status: str
    created_at: datetime
    source: str = "simple_rt"

    model_config = {"from_attributes": True}


class TrialIn(BaseModel):
    trial_index: int = Field(ge=0)
    trial_type: str = "test"
    stimulus_id: str = "go"
    response: str | None = None
    correct: bool | None = None
    rt_ms: float | None = None
    client_ts: datetime | None = None


class TrialBatchIn(BaseModel):
    trials: list[TrialIn]


class TrialOut(BaseModel):
    id: uuid.UUID
    trial_index: int
    trial_type: str
    stimulus_id: str
    response: str | None
    correct: bool | None
    rt_ms: float | None
    flagged: bool
    flag_reason: str | None

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    session_id: uuid.UUID
    n_test_trials: int
    n_valid_trials: int
    n_flagged_trials: int
    mean_rt_ms: float | None
    median_rt_ms: float | None
    sd_rt_ms: float | None
    accuracy: float | None
    score: float | None
    qc_flag_any: bool
    qc_notes: str | None

    model_config = {"from_attributes": True}


class CompleteOut(BaseModel):
    session: SessionOut
    summary: SummaryOut
