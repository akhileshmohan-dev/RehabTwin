import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from uuid import uuid4
from sqlalchemy import func

from backend.repositories.interfaces import (
    IPatientRepository,
    ISessionRepository,
    ITelemetryRepository,
    IResultRepository,
)
from digital_thread.db import Database
from digital_thread.models import Session, Frame, Result, utc_now


class SQLAlchemyPatientRepository(IPatientRepository):
    def __init__(self, db: Database):
        self.db = db

    def list_patients(self) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            records = (
                session.query(
                    Session.patient_id,
                    func.count(Session.session_id).label("session_count"),
                    func.max(Session.started_at).label("last_active")
                )
                .group_by(Session.patient_id)
                .all()
            )
            
            output = []
            for rec in records:
                output.append({
                    "patient_id": rec.patient_id,
                    "total_sessions": rec.session_count,
                    "last_active": rec.last_active.isoformat() if rec.last_active else None
                })
            return output

    def get_patient_history(self, patient_id: str) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            rows = session.query(Session).filter(Session.patient_id == patient_id).order_by(Session.started_at).all()
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


class SQLAlchemySessionRepository(ISessionRepository):
    def __init__(self, db: Database):
        self.db = db

    def start_session(self, patient_id: str, exercise: str, session_id: Optional[str] = None) -> str:
        sid = session_id or f"S-{uuid4().hex[:10].upper()}"
        with self.db.session() as session:
            session.add(Session(
                session_id=sid,
                patient_id=patient_id,
                exercise=exercise,
                started_at=utc_now(),
                status="ACTIVE",
            ))
            session.commit()
        return sid

    def get_session(self, session_id: str) -> Dict[str, Any]:
        with self.db.session() as session:
            s = session.get(Session, session_id)
            if not s:
                raise KeyError(session_id)
            return {
                "session_id": s.session_id,
                "patient_id": s.patient_id,
                "exercise": s.exercise,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "status": s.status,
            }

    def end_session(self, session_id: str) -> None:
        with self.db.session() as session:
            s = session.get(Session, session_id)
            if s:
                s.ended_at = utc_now()
                s.status = "COMPLETED"
                session.commit()

    def get_sessions_by_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            rows = session.query(Session).filter(Session.patient_id == patient_id).order_by(Session.started_at).all()
            output = []
            for s in rows:
                output.append({
                    "session_id": s.session_id,
                    "patient_id": s.patient_id,
                    "exercise": s.exercise,
                    "started_at": s.started_at.isoformat(),
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "status": s.status,
                })
            return output

    def export_session(self, session_id: str, output_path: str) -> str:
        with self.db.session() as db_session:
            s = db_session.get(Session, session_id)
            if not s:
                raise KeyError(session_id)
            payload = {
                "session": {
                    "session_id": s.session_id,
                    "patient_id": s.patient_id,
                    "exercise": s.exercise,
                    "started_at": s.started_at.isoformat(),
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "status": s.status,
                },
                "frames": [
                    {
                        "frame_id": f.frame_id,
                        "timestamp": f.timestamp.isoformat(),
                        "landmarks": f.landmarks,
                        "joint_angles": f.joint_angles,
                        "phase": f.phase,
                    }
                    for f in s.frames
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
                    for r in s.results
                ],
            }
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return str(out)


class SQLAlchemyTelemetryRepository(ITelemetryRepository):
    def __init__(self, db: Database):
        self.db = db

    def record_frame(
        self,
        session_id: str,
        frame_id: int,
        landmarks: Dict[str, Any],
        joint_angles: Dict[str, float],
        phase: Optional[str] = None,
    ) -> None:
        with self.db.session() as session:
            session.add(Frame(
                session_id=session_id,
                frame_id=frame_id,
                timestamp=utc_now(),
                landmarks=landmarks,
                joint_angles=joint_angles,
                phase=phase,
            ))
            session.commit()


class SQLAlchemyResultRepository(IResultRepository):
    def __init__(self, db: Database):
        self.db = db

    def record_result(
        self,
        session_id: str,
        repetitions: int,
        rom_min: Optional[float],
        rom_max: Optional[float],
        rom_average: Optional[float],
        performance_score: Optional[float],
        feedback: str = "",
    ) -> None:
        with self.db.session() as session:
            s = session.get(Session, session_id)
            if not s:
                raise RuntimeError(f"Session {session_id} does not exist.")
            
            existing_result = session.query(Result).filter_by(session_id=session_id).first()
            if existing_result:
                existing_result.repetitions = repetitions
                existing_result.rom_min = rom_min
                existing_result.rom_max = rom_max
                existing_result.rom_average = rom_average
                existing_result.performance_score = performance_score
                existing_result.feedback = feedback
            else:
                session.add(Result(
                    session_id=session_id,
                    exercise=s.exercise,
                    repetitions=repetitions,
                    rom_min=rom_min,
                    rom_max=rom_max,
                    rom_average=rom_average,
                    performance_score=performance_score,
                    feedback=feedback,
                ))
            session.commit()

    def get_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            r = session.query(Result).filter_by(session_id=session_id).first()
            if not r:
                return None
            return {
                "exercise": r.exercise,
                "repetitions": r.repetitions,
                "rom_min": r.rom_min,
                "rom_max": r.rom_max,
                "rom_average": r.rom_average,
                "performance_score": r.performance_score,
                "feedback": r.feedback,
            }
