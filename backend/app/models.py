from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(String(128), default="simple_rt")
    source: Mapped[str] = mapped_column(String(32), default="simple_rt")  # simple_rt | tmb_run
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | complete | incomplete
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    referer: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_data_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_outcomes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trials: Mapped[list[TrialRow]] = relationship(back_populates="session", cascade="all, delete-orphan")
    summary: Mapped[SummaryRow | None] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class TrialRow(Base):
    __tablename__ = "trials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), index=True)
    trial_index: Mapped[int] = mapped_column(Integer)
    trial_type: Mapped[str] = mapped_column(String(32), default="test")  # practice | test
    stimulus_id: Mapped[str] = mapped_column(String(64), default="go")
    response: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[SessionRow] = relationship(back_populates="trials")


class SummaryRow(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), unique=True, index=True
    )
    n_test_trials: Mapped[int] = mapped_column(Integer, default=0)
    n_valid_trials: Mapped[int] = mapped_column(Integer, default=0)
    n_flagged_trials: Mapped[int] = mapped_column(Integer, default=0)
    mean_rt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_rt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    sd_rt_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    qc_flag_any: Mapped[bool] = mapped_column(Boolean, default=False)
    qc_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[SessionRow] = relationship(back_populates="summary")
