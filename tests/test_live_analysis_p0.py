"""
P0 regression tests for rehabilitation/live_analysis.py.

P0-1: The hard-coded patient ("TEST-001") must exist before
      DigitalThread.start_session(), which raises for unknown patients.
P0-2: DigitalThread is stateful; record_frame/record_result/end_session must
      be called WITHOUT a session_id argument (start_session stores it).
"""
import ast
import tempfile
from pathlib import Path

import pytest

from backend.repositories.interfaces import PatientNotFoundInRepoException
from digital_thread.thread import DigitalThread

LIVE_ANALYSIS_PATH = Path(__file__).resolve().parents[1] / "rehabilitation" / "live_analysis.py"


def _parse_live_analysis():
    source = LIVE_ANALYSIS_PATH.read_text(encoding="utf-8")
    return ast.parse(source)


def _method_calls(tree, method_name):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method_name
    ]


def _make_thread():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    thread = DigitalThread(database_url=f"sqlite:///{tmp.name}")
    return thread, Path(tmp.name)


def _dispose(thread, path):
    thread.db.engine.dispose()
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# P0-2: stateful API must not be passed session_id
# ---------------------------------------------------------------------------

def test_live_analysis_does_not_pass_session_id():
    tree = _parse_live_analysis()
    for method_name in ("record_frame", "record_result", "end_session"):
        calls = _method_calls(tree, method_name)
        assert calls, f"expected live_analysis.py to call {method_name}()"
        for call in calls:
            kwargs = {kw.arg for kw in call.keywords}
            assert "session_id" not in kwargs, (
                f"digital_thread.{method_name}() must not receive session_id"
            )


# ---------------------------------------------------------------------------
# P0-1: patient must be ensured before start_session
# ---------------------------------------------------------------------------

def test_live_analysis_ensures_patient_before_start_session():
    tree = _parse_live_analysis()

    helper_defs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_ensure_patient"
    ]
    assert helper_defs, "live_analysis.py must define an _ensure_patient helper"

    helper_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_ensure_patient"
    ]
    assert helper_calls, "_ensure_patient() must be called in live_analysis.py"

    start_calls = _method_calls(tree, "start_session")
    assert start_calls, "expected live_analysis.py to call start_session()"

    assert min(call.lineno for call in helper_calls) < min(
        call.lineno for call in start_calls
    ), "_ensure_patient() must run before start_session()"

    # The helper must reuse the repository pattern, not raw SQL.
    helper_source = ast.unparse(helper_defs[0])
    assert "patient_exists" in helper_source
    assert "create_patient" in helper_source


# ---------------------------------------------------------------------------
# Functional contract of the stateful DigitalThread used by live_analysis
# ---------------------------------------------------------------------------

def test_digital_thread_stateful_api_without_session_id():
    thread, path = _make_thread()
    try:
        thread.patient_repo.create_patient({
            "patient_id": "TEST-001",
            "name": "Live Analysis Patient",
            "status": "ACTIVE",
        })

        sid = thread.start_session(patient_id="TEST-001", exercise="elbow_flexion")
        assert thread.session_id == sid

        thread.record_frame(
            frame_id=1,
            landmarks={"LEFT_ELBOW": {"x": 1.0, "y": 2.0}},
            joint_angles={"left_elbow": 90.0},
            phase="MOVING",
        )
        thread.record_result(
            repetitions=1,
            rom_min=90.0,
            rom_max=170.0,
            rom_average=None,
            performance_score=None,
            feedback="",
        )
        assert thread.result_repo.get_result(sid) is not None

        thread.end_session()
        assert thread.session_id is None
    finally:
        _dispose(thread, path)


def test_start_session_fails_for_missing_patient():
    thread, path = _make_thread()
    try:
        with pytest.raises(PatientNotFoundInRepoException):
            thread.start_session(patient_id="TEST-001", exercise="elbow_flexion")
    finally:
        _dispose(thread, path)
