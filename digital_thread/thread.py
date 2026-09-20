from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4
import json

from .db import Database
from .models import Session, Frame, Result, utc_now


class DigitalThread:
    """Database-agnostic digital-thread API for RehabTwin.

    Change DATABASE_URL from SQLite to PostgreSQL without changing callers.
    """

    def __init__(self, database_url: Optional[str] = None):
        self.db = Database(database_url) if database_url else Database()
        self.db.create_schema()
        self.session_id: Optional[str] = None

    def start_session(self, patient_id: str, exercise: str, session_id: Optional[str] = None) -> str:
        sid = session_id or f"S-{uuid4().hex[:10].upper()}"
        with self.db.session() as db:
            db.add(Session(
                session_id=sid,
                patient_id=patient_id,
                exercise=exercise,
                started_at=utc_now(),
                status="ACTIVE",
            ))
            db.commit()
        self.session_id = sid
        return sid

    def record_frame(
        self,
        frame_id: int,
        landmarks: Dict[str, Any],
        joint_angles: Dict[str, float],
        phase: Optional[str] = None,
    ) -> None:
        if not self.session_id:
            raise RuntimeError("No active digital-thread session.")
        with self.db.session() as db:
            db.add(Frame(
                session_id=self.session_id,
                frame_id=frame_id,
                timestamp=utc_now(),
                landmarks=landmarks,
                joint_angles=joint_angles,
                phase=phase,
            ))
            db.commit()

    def record_result(
        self,
        repetitions: int,
        rom_min: Optional[float],
        rom_max: Optional[float],
        rom_average: Optional[float],
        performance_score: Optional[float],
        feedback: str = "",
    ) -> None:
        if not self.session_id:
            raise RuntimeError("No active digital-thread session.")
        with self.db.session() as db:
            session = db.get(Session, self.session_id)
            if session is None:
                raise RuntimeError(f"Session {self.session_id} does not exist.")
            db.add(Result(
                session_id=self.session_id,
                exercise=session.exercise,
                repetitions=repetitions,
                rom_min=rom_min,
                rom_max=rom_max,
                rom_average=rom_average,
                performance_score=performance_score,
                feedback=feedback,
            ))
            db.commit()

    def end_session(self) -> None:
        if not self.session_id:
            return
        with self.db.session() as db:
            session = db.get(Session, self.session_id)
            if session:
                session.ended_at = utc_now()
                session.status = "COMPLETED"
                db.commit()
        self.session_id = None

    def get_session(self, session_id: str) -> Dict[str, Any]:
        with self.db.session() as db:
            session = db.get(Session, session_id)
            if not session:
                raise KeyError(session_id)
            return {
                "session_id": session.session_id,
                "patient_id": session.patient_id,
                "exercise": session.exercise,
                "started_at": session.started_at.isoformat(),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "status": session.status,
            }

    def history(self, patient_id: str) -> list[Dict[str, Any]]:
        with self.db.session() as db:
            rows = db.query(Session).filter(Session.patient_id == patient_id).order_by(Session.started_at).all()
            output = []
            for s in rows:
                output.append({
                    "session_id": s.session_id,
                    "patient_id": s.patient_id,
                    "exercise": s.exercise,
                    "started_at": s.started_at.isoformat(),
                    "status": s.status,
                    "results": [
                        {
                            "repetitions": r.repetitions,
                            "rom_min": r.rom_min,
                            "rom_max": r.rom_max,
                            "rom_average": r.rom_average,
                            "performance_score": r.performance_score,
                            "feedback": r.feedback,
                        }
                        for r in s.results
                    ],
                })
            return output

    def export_session(self, session_id: str, output_path: str) -> str:
        with self.db.session() as db:
            session = db.get(Session, session_id)
            if not session:
                raise KeyError(session_id)
            payload = {
                "session": self.get_session(session_id),
                "frames": [
                    {
                        "frame_id": f.frame_id,
                        "timestamp": f.timestamp.isoformat(),
                        "landmarks": f.landmarks,
                        "joint_angles": f.joint_angles,
                        "phase": f.phase,
                    }
                    for f in session.frames
                ],
                "results": [
                    {
                        "exercise": r.exercise,
                        "repetitions": r.repetitions,
                        "rom_min": r.rom_min,
                        "rom_max": r.rom_max,
                        "rom_average": r.rom_average,
                        "performance_score": r.performance_score,
                        "feedback": r.feedback,
                    }
                    for r in session.results
                ],
            }
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(out)
