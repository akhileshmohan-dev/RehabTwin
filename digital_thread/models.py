from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    exercise: Mapped[str] = mapped_column(String(128), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False, default="left")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

    frames: Mapped[list["Frame"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Frame.frame_id"
    )
    results: Mapped[list["Result"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Frame(Base):
    __tablename__ = "frames"
    __table_args__ = (UniqueConstraint("session_id", "frame_id", name="uq_frame_session_frame"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id", ondelete="CASCADE"), index=True)
    frame_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    landmarks: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    joint_angles: Mapped[Dict[str, float]] = mapped_column(JSON, nullable=False)
    phase: Mapped[Optional[str]] = mapped_column(String(64))

    session: Mapped[Session] = relationship(back_populates="frames")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id", ondelete="CASCADE"), unique=True, index=True)
    exercise: Mapped[str] = mapped_column(String(128), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False, default="left")
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False)
    rom_min: Mapped[Optional[float]] = mapped_column(Float)
    rom_max: Mapped[Optional[float]] = mapped_column(Float)
    rom_average: Mapped[Optional[float]] = mapped_column(Float)
    performance_score: Mapped[Optional[float]] = mapped_column(Float)
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")

    session: Mapped[Session] = relationship(back_populates="results")
