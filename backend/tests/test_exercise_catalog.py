"""
Tests for the CSV-driven exercise catalog, the catalog-backed
GET /api/analysis/exercises endpoint, and the single-row CSV export.

Covers catalog loading/validation errors, endpoint output, and export column
order.
"""
import csv
import io
import os
import tempfile
import unittest
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.exercise_catalog import (
    ExerciseCatalogError,
    clear_catalog_cache,
    catalog_row_for_registry_key,
    load_catalog,
)
from backend.services.session_service import CSV_EXPORT_COLUMNS
from digital_thread.db import Database
from digital_thread.models import Patient
from backend.repositories.sqlalchemy_impl import (
    SQLAlchemyPatientRepository,
    SQLAlchemySessionRepository,
    SQLAlchemyTelemetryRepository,
    SQLAlchemyResultRepository,
)
from backend.core.dependencies import (
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
    get_patient_repo,
    get_assignment_repo,
)


HEADER = "exercise_id,exercise_name,target_joint,side,rom_min_deg,rom_max_deg,target_reps\n"


# ---------------------------------------------------------------------------
# Catalog loader
# ---------------------------------------------------------------------------

def _write_catalog(tmp_path: Path, body: str) -> str:
    path = tmp_path / "catalog.csv"
    path.write_text(HEADER + body, encoding="utf-8", newline="\n")
    return str(path)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_catalog_cache()
    yield
    clear_catalog_cache()


def test_default_catalog_loads_two_rows():
    rows = load_catalog()
    assert len(rows) == 2

    elbow = rows[0]
    assert elbow["exercise_id"] == "ELBOW_FLEX"
    assert elbow["exercise_name"] == "Elbow Flexion"
    assert elbow["target_joint"] == "elbow"
    assert elbow["side"] == "both"
    assert elbow["rom_min_deg"] == 40.0
    assert isinstance(elbow["rom_min_deg"], float)
    assert elbow["rom_max_deg"] == 160.0
    assert elbow["target_reps"] == 10
    assert isinstance(elbow["target_reps"], int)
    assert elbow["registry_key"] == "elbow_flexion"

    shoulder = rows[1]
    assert shoulder["exercise_id"] == "SHOULDER_FLEX"
    assert shoulder["registry_key"] == "shoulder_flexion"


def test_env_override_changes_catalog(monkeypatch, tmp_path):
    custom = _write_catalog(
        tmp_path,
        "KNEE_FLEX,Knee Flexion,knee,left,100,160,5\n",
    )
    monkeypatch.setenv("EXERCISE_CATALOG_PATH", custom)
    rows = load_catalog()
    assert len(rows) == 1
    assert rows[0]["exercise_id"] == "KNEE_FLEX"
    assert rows[0]["side"] == "left"
    assert rows[0]["registry_key"] is None


def test_missing_file_raises(tmp_path):
    with pytest.raises(ExerciseCatalogError, match="not found"):
        load_catalog(path=str(tmp_path / "missing.csv"))


def test_missing_column_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("exercise_id,exercise_name\ne1,name\n", encoding="utf-8", newline="\n")
    with pytest.raises(ExerciseCatalogError, match="missing required columns"):
        load_catalog(path=str(path))


def test_invalid_side_raises(tmp_path):
    path = _write_catalog(tmp_path, "ELBOW_FLEX,Elbow Flexion,elbow,centre,40,160,10\n")
    with pytest.raises(ExerciseCatalogError, match="invalid side"):
        load_catalog(path=path)


def test_non_numeric_rom_raises(tmp_path):
    path = _write_catalog(tmp_path, "ELBOW_FLEX,Elbow Flexion,elbow,both,forty,160,10\n")
    with pytest.raises(ExerciseCatalogError, match="rom_min_deg"):
        load_catalog(path=path)


def test_non_integer_reps_raises(tmp_path):
    path = _write_catalog(tmp_path, "ELBOW_FLEX,Elbow Flexion,elbow,both,40,160,abc\n")
    with pytest.raises(ExerciseCatalogError, match="target_reps"):
        load_catalog(path=path)


def test_catalog_row_for_registry_key():
    assert catalog_row_for_registry_key("elbow_flexion")["exercise_id"] == "ELBOW_FLEX"
    assert catalog_row_for_registry_key("knee_flexion") is None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def test_exercises_endpoint_returns_catalog(monkeypatch):
    monkeypatch.delenv("EXERCISE_CATALOG_PATH", raising=False)
    clear_catalog_cache()
    app.dependency_overrides.clear()
    client = TestClient(app)
    resp = client.get("/api/analysis/exercises")
    assert resp.status_code == 200

    body = resp.json()
    assert body["total"] == 2
    by_id = {ex["id"]: ex for ex in body["exercises"]}
    assert set(by_id) == {"elbow_flexion", "shoulder_flexion"}

    elbow = by_id["elbow_flexion"]
    assert elbow["exercise_id"] == "ELBOW_FLEX"
    assert elbow["exercise_name"] == "Elbow Flexion"
    assert elbow["name"] == "Elbow Flexion"
    assert elbow["target_joint"] == "elbow"
    assert elbow["side"] == "both"
    assert elbow["supported_sides"] == ["left", "right"]
    assert elbow["rom_min_deg"] == 40.0
    assert elbow["rom_max_deg"] == 160.0
    assert elbow["target_reps"] == 10
    assert elbow["registry_key"] == "elbow_flexion"

    shoulder = by_id["shoulder_flexion"]
    assert shoulder["rom_min_deg"] == 30.0
    assert shoulder["rom_max_deg"] == 160.0
    assert shoulder["target_reps"] == 8


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def _make_file_db() -> Database:
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database(f"sqlite:///{tmp.name}?check_same_thread=False")
    db.create_schema()
    db._test_path = tmp.name
    return db


def _cleanup_db(db):
    db.engine.dispose()
    try:
        os.remove(db._test_path)
    except OSError:
        pass


class TestSessionCsvExport(unittest.TestCase):

    def setUp(self):
        self.db = _make_file_db()
        self.patient_repo = SQLAlchemyPatientRepository(self.db)
        self.session_repo = SQLAlchemySessionRepository(self.db)
        self.result_repo = SQLAlchemyResultRepository(self.db)
        app.dependency_overrides[get_session_repo] = lambda: self.session_repo
        app.dependency_overrides[get_telemetry_repo] = lambda: SQLAlchemyTelemetryRepository(self.db)
        app.dependency_overrides[get_result_repo] = lambda: self.result_repo
        app.dependency_overrides[get_patient_repo] = lambda: self.patient_repo
        app.dependency_overrides[get_assignment_repo] = lambda: None
        self.client = TestClient(app, raise_server_exceptions=False)
        self.patient_repo.create_patient({"patient_id": "P_EXPORT", "name": "Export Patient", "status": "ACTIVE"})

    def tearDown(self):
        app.dependency_overrides.clear()
        _cleanup_db(self.db)

    def _make_session(self, side="left"):
        sid = self.session_repo.start_session("P_EXPORT", "elbow_flexion", side=side)
        self.result_repo.record_result(
            session_id=sid,
            repetitions=10,
            rom_min=40.0,
            rom_max=160.0,
            rom_average=100.0,
            performance_score=92.3,
            feedback="great",
        )
        return sid

    def test_export_csv_column_order_and_values(self):
        sid = self._make_session(side="left")
        resp = self.client.get(f"/api/sessions/{sid}/export.csv")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp.headers["content-type"])

        rows = list(csv.reader(io.StringIO(resp.text)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], CSV_EXPORT_COLUMNS)
        self.assertEqual(rows[0], [
            "exercise_id", "exercise_name", "target_joint", "side",
            "rom_min_deg", "rom_max_deg", "target_reps",
            "session_id", "patient_id", "repetitions", "rom_min", "rom_max",
            "performance_score",
        ])

        row = rows[1]
        self.assertEqual(row[0], "ELBOW_FLEX")
        self.assertEqual(row[1], "Elbow Flexion")
        self.assertEqual(row[2], "elbow")
        self.assertEqual(row[3], "left")
        self.assertEqual(row[4], "40")
        self.assertEqual(row[5], "160")
        self.assertEqual(row[6], "10")
        self.assertEqual(row[7], sid)
        self.assertEqual(row[8], "P_EXPORT")
        self.assertEqual(row[9], "10")
        self.assertEqual(row[10], "40")
        self.assertEqual(row[11], "160")
        self.assertEqual(row[12], "92.3")

    def test_export_csv_uses_session_actual_side(self):
        sid = self._make_session(side="right")
        resp = self.client.get(f"/api/sessions/{sid}/export.csv")
        self.assertEqual(resp.status_code, 200)
        row = list(csv.reader(io.StringIO(resp.text)))[1]
        self.assertEqual(row[3], "right")
        self.assertEqual(row[0], "ELBOW_FLEX")

    def test_export_csv_unknown_session_404(self):
        resp = self.client.get("/api/sessions/NOPE/export.csv")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
