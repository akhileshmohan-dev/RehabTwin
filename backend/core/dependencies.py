"""
FastAPI dependency injection utilities for RehabTwin backend services.
"""
from typing import Generator
from backend.repositories.interfaces import (
    IPatientRepository,
    ISessionRepository,
    ITelemetryRepository,
    IResultRepository,
)
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from digital_thread.db import Database
from digital_thread.thread import DigitalThread

# Global instances
_db_instance: Database | None = None
_digital_thread_instance: DigitalThread | None = None


def get_database() -> Database:
    """Dependency getter for the core Database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.create_schema()
    return _db_instance


def get_patient_repo() -> IPatientRepository:
    return SQLAlchemyPatientRepository(get_database())


def get_session_repo() -> ISessionRepository:
    return SQLAlchemySessionRepository(get_database())


def get_telemetry_repo() -> ITelemetryRepository:
    return SQLAlchemyTelemetryRepository(get_database())


def get_result_repo() -> IResultRepository:
    return SQLAlchemyResultRepository(get_database())


def get_digital_thread() -> DigitalThread:
    """
    Dependency getter for DigitalThread persistence instance.
    Maintained as a legacy facade.
    """
    global _digital_thread_instance
    if _digital_thread_instance is None:
        _digital_thread_instance = DigitalThread()
    return _digital_thread_instance


def set_digital_thread_instance(instance: DigitalThread | None) -> None:
    """Helper to set or override the DigitalThread instance (useful for unit testing)."""
    global _digital_thread_instance
    _digital_thread_instance = instance
