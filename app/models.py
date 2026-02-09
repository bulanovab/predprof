from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from .db import Base


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    seats = Column(Integer, nullable=False)


class Applicant(Base):
    __tablename__ = "applicants"

    id = Column(Integer, primary_key=True)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True)
    day = Column(String, nullable=False, index=True)
    imported_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    applications = relationship("ApplicationSnapshot", back_populates="snapshot")


class ApplicationSnapshot(Base):
    __tablename__ = "application_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("snapshots.id"), nullable=False, index=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False, index=True)

    consent = Column(Boolean, nullable=False)
    priority = Column(Integer, nullable=False)
    physics_ikt = Column(Integer, nullable=False)
    russian = Column(Integer, nullable=False)
    math = Column(Integer, nullable=False)
    achievements = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)

    snapshot = relationship("Snapshot", back_populates="applications")

    __table_args__ = (
        UniqueConstraint("snapshot_id", "applicant_id", "program_id", name="uq_snapshot_app_program"),
    )


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False, index=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False, index=True)

    consent = Column(Boolean, nullable=False)
    priority = Column(Integer, nullable=False)
    physics_ikt = Column(Integer, nullable=False)
    russian = Column(Integer, nullable=False)
    math = Column(Integer, nullable=False)
    achievements = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    day = Column(String, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("applicant_id", "program_id", name="uq_current_app_program"),
    )