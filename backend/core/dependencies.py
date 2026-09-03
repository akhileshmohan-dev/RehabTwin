"""
FastAPI dependency injection utilities for RehabTwin backend services.
"""
from typing import Generator
from digital_thread.thread import DigitalThread

# Global shared DigitalThread instance for default DI
_digital_thread_instance: DigitalThread | None = None


def get_digital_thread() -> DigitalThread:
    """Dependency getter for DigitalThread persistence instance."""
    global _digital_thread_instance
    if _digital_thread_instance is None:
        _digital_thread_instance = DigitalThread()
    return _digital_thread_instance


def set_digital_thread_instance(instance: DigitalThread | None) -> None:
    """Helper to set or override the DigitalThread instance (useful for unit testing)."""
    global _digital_thread_instance
    _digital_thread_instance = instance
