import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from uuid import uuid4
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError

from backend.repositories.interfaces import (
    IPatientRepository,
    IAssignmentRepository,
    ISessionRepository,
    ITelemetryRepository,
    IResultRepository,
    PatientNotFoundInRepoException,
)
from digital_thread.db import Database
from digital_thread.models import Patient, PatientExerciseAssignment, Session, Frame, Result, utc_now


class SQLAlchemyPatientRepository(IPatientRepository):
    def __init__(self, db: Database):
        self.db = db

    def create_patient(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.db.session() as session:
            patient = Patient(
                patient_id=data["patient_id"],
                name=data["name"],
                age=data.get("age"),
                gender=data.get("gender"),
                phone=data.get("phone"),
                email=data.get("email"),
                notes=data.get("notes"),
                status=data.get("status", "ACTIVE"),
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(patient)
            session.commit()
            return self._to_dict(patient)

    def get_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            p = session.query(Patient).filter(Patient.patient_id == patient_id).first()
            if not p:
                return None
            return self._to_dict(p)

    def patient_exists(self, patient_id: str) -> bool:
        with self.db.session() as session:
            return session.query(Patient.patient_id).filter(Patient.patient_id == patient_id).first() is not None

    def update_patient(self, patient_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            p = session.query(Patient).filter(Patient.patient_id == patient_id).first()
            if not p:
                return None
            for key in ("name", "age", "gender", "phone", "email", "notes", "status"):
                if key in updates and updates[key] is not None:
                    setattr(p, key, updates[key])
            p.updated_at = utc_now()
            session.commit()
            return self._to_dict(p)

    def deactivate_patient(self, patient_id: str) -> Optional[Dict[str, Any]]:
        return self.update_patient(patient_id, {"status": "INACTIVE"})

    def list_patients(self) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            records = (
                session.query(
                    Patient,
                    func.count(Session.session_id).label("total_sessions"),
                    func.sum(case((Session.status == "ACTIVE", 1), else_=0)).label("active_sessions"),
                    func.sum(case((Session.status == "COMPLETED", 1), else_=0)).label("completed_sessions"),
                    func.max(Session.started_at).label("last_active"),
                    func.avg(
                        case(
                            ((Session.status == "COMPLETED") & (Result.performance_score.is_not(None)), Result.performance_score),
                            else_=None
                        )
                    ).label("avg_score"),
                )
                .outerjoin(Session, Patient.patient_id == Session.patient_id)
                .outerjoin(Result, Session.session_id == Result.session_id)
                .group_by(Patient.patient_id)
                .order_by(Patient.patient_id)
                .all()
            )
            
            output = []
            for patient, total_sessions, active_sessions, completed_sessions, last_active, avg_score in records:
                output.append({
                    "patient_id": patient.patient_id,
                    "name": patient.name,
                    "status": patient.status,
                    "age": patient.age,
                    "gender": patient.gender,
                    "phone": patient.phone,
                    "email": patient.email,
                    "notes": patient.notes,
                    "created_at": patient.created_at.isoformat() if patient.created_at else None,
                    "updated_at": patient.updated_at.isoformat() if patient.updated_at else None,
                    "total_sessions": int(total_sessions or 0),
                    "active_sessions": int(active_sessions or 0),
                    "completed_sessions": int(completed_sessions or 0),
                    "last_active": last_active.isoformat() if last_active else None,
                    "average_performance_score": round(float(avg_score), 1) if avg_score is not None else None,
                })
            return output

    def get_system_overview(self) -> Dict[str, Any]:
        with self.db.session() as session:
            total_patients = session.query(func.count(Patient.patient_id)).scalar() or 0
            total_sessions = session.query(func.count(Session.session_id)).scalar() or 0
            active_patients = (
                session.query(func.count(func.distinct(Session.patient_id)))
                .filter(Session.status == "ACTIVE")
                .scalar() or 0
            )
            avg_score = (
                session.query(func.avg(Result.performance_score))
                .join(Session, Session.session_id == Result.session_id)
                .filter(Session.status == "COMPLETED")
                .scalar()
            )
            return {
                "total_patients": int(total_patients),
                "total_sessions": int(total_sessions),
                "active_patients": int(active_patients),
                "average_performance_score": round(float(avg_score), 1) if avg_score is not None else None,
            }

    def get_patient_history(self, patient_id: str) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            rows = (
                session.query(Session)
                .filter(Session.patient_id == patient_id)
                .order_by(Session.started_at.desc())
                .all()
            )
            output = []
            for s in rows:
                sess_side = getattr(s, "side", "left") or "left"
                output.append({
                    "session_id": s.session_id,
                    "patient_id": s.patient_id,
                    "exercise": s.exercise,
                    "side": sess_side,
                    "started_at": s.started_at.isoformat(),
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "status": s.status,
                    "results": [
                        {
                            "repetitions": r.repetitions,
                            "side": getattr(r, "side", sess_side) or sess_side,
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

    @staticmethod
    def _to_dict(p: Patient) -> Dict[str, Any]:
        return {
            "patient_id": p.patient_id,
            "name": p.name,
            "age": p.age,
            "gender": p.gender,
            "phone": p.phone,
            "email": p.email,
            "notes": p.notes,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }


class SQLAlchemyAssignmentRepository(IAssignmentRepository):
    def __init__(self, db: Database):
        self.db = db

    def assign_exercise(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self.db.session() as session:
            assignment = PatientExerciseAssignment(
                patient_id=data["patient_id"],
                exercise_id=data["exercise_id"],
                side=(data.get("side") or "left").strip().lower(),
                target_rom=data.get("target_rom"),
                target_repetitions=data.get("target_repetitions"),
                sessions_per_day=data.get("sessions_per_day", 1),
                notes=data.get("notes", "") or "",
                active=data.get("active", True),
                assigned_at=utc_now(),
                updated_at=utc_now(),
            )
            session.add(assignment)
            session.commit()
            return self._to_dict(assignment)

    def get_assignment(self, assignment_id: int) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            a = session.query(PatientExerciseAssignment).filter(PatientExerciseAssignment.id == assignment_id).first()
            if not a:
                return None
            return self._to_dict(a)

    def get_assignment_by_exercise_and_side(
        self, patient_id: str, exercise_id: str, side: str
    ) -> Optional[Dict[str, Any]]:
        norm_side = (side or "left").strip().lower()
        with self.db.session() as session:
            a = (
                session.query(PatientExerciseAssignment)
                .filter(
                    PatientExerciseAssignment.patient_id == patient_id,
                    PatientExerciseAssignment.exercise_id == exercise_id,
                    PatientExerciseAssignment.side == norm_side,
                )
                .first()
            )
            if not a:
                return None
            return self._to_dict(a)

    def list_assignments(self, patient_id: str, active_only: bool = False) -> List[Dict[str, Any]]:
        with self.db.session() as session:
            q = session.query(PatientExerciseAssignment).filter(PatientExerciseAssignment.patient_id == patient_id)
            if active_only:
                q = q.filter(PatientExerciseAssignment.active == True)
            assignments = q.order_by(PatientExerciseAssignment.assigned_at.desc()).all()
            return [self._to_dict(a) for a in assignments]

    def update_assignment(self, assignment_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            a = session.query(PatientExerciseAssignment).filter(PatientExerciseAssignment.id == assignment_id).first()
            if not a:
                return None
            for key in ("target_rom", "target_repetitions", "sessions_per_day", "notes", "active"):
                if key in updates and updates[key] is not None:
                    setattr(a, key, updates[key])
            a.updated_at = utc_now()
            session.commit()
            return self._to_dict(a)

    def deactivate_assignment(self, assignment_id: int) -> Optional[Dict[str, Any]]:
        return self.update_assignment(assignment_id, {"active": False})

    @staticmethod
    def _to_dict(a: PatientExerciseAssignment) -> Dict[str, Any]:
        return {
            "id": a.id,
            "patient_id": a.patient_id,
            "exercise_id": a.exercise_id,
            "side": a.side,
            "target_rom": a.target_rom,
            "target_repetitions": a.target_repetitions,
            "sessions_per_day": a.sessions_per_day,
            "notes": a.notes,
            "active": a.active,
            "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }


class SQLAlchemySessionRepository(ISessionRepository):
    def __init__(self, db: Database):
        self.db = db

    def start_session(self, patient_id: str, exercise: str, side: str = "left", session_id: Optional[str] = None) -> str:
        sid = session_id or f"S-{uuid4().hex[:10].upper()}"
        normalized_side = (side or "left").strip().lower()
        with self.db.session() as session:
            p = session.query(Patient).filter(Patient.patient_id == patient_id).first()
            if not p:
                raise PatientNotFoundInRepoException(patient_id)
            session.add(Session(
                session_id=sid,
                patient_id=patient_id,
                exercise=exercise,
                side=normalized_side,
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
                "side": getattr(s, "side", "left") or "left",
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "status": s.status,
            }

    def end_session(self, session_id: str) -> None:
        with self.db.session() as session:
            s = session.get(Session, session_id)
            if s and s.status != "COMPLETED":
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
                    "side": getattr(s, "side", "left") or "left",
                    "started_at": s.started_at.isoformat(),
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "status": s.status,
                })
            return output

    def export_session(self, session_id: str, output_path: str) -> str:
        with self.db.session() as session:
            s = session.get(Session, session_id)
            if not s:
                raise KeyError(session_id)
            data = {
                "session_id": s.session_id,
                "patient_id": s.patient_id,
                "exercise": s.exercise,
                "side": getattr(s, "side", "left") or "left",
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "status": s.status,
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
                        "side": getattr(r, "side", "left") or "left",
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
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(data, f, indent=2)
        return str(p.resolve())


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
            s = session.get(Session, session_id)
            if not s:
                raise KeyError(session_id)
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
                raise KeyError(session_id)

            existing = session.query(Result).filter_by(session_id=session_id).first()
            if existing:
                existing.repetitions = repetitions
                existing.rom_min = rom_min
                existing.rom_max = rom_max
                existing.rom_average = rom_average
                existing.performance_score = performance_score
                existing.feedback = feedback
                session.commit()
                return

            session_side = getattr(s, "side", "left") or "left"
            try:
                session.add(Result(
                    session_id=session_id,
                    exercise=s.exercise,
                    side=session_side,
                    repetitions=repetitions,
                    rom_min=rom_min,
                    rom_max=rom_max,
                    rom_average=rom_average,
                    performance_score=performance_score,
                    feedback=feedback,
                ))
                session.commit()
            except IntegrityError:
                session.rollback()
                # Row was concurrently inserted by another thread. Fetch and update it.
                existing_result = session.query(Result).filter_by(session_id=session_id).first()
                if existing_result:
                    existing_result.repetitions = repetitions
                    existing_result.rom_min = rom_min
                    existing_result.rom_max = rom_max
                    existing_result.rom_average = rom_average
                    existing_result.performance_score = performance_score
                    existing_result.feedback = feedback
                    session.commit()

    def get_result(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.db.session() as session:
            r = session.query(Result).filter_by(session_id=session_id).first()
            if not r:
                return None
            return {
                "exercise": r.exercise,
                "side": getattr(r, "side", "left") or "left",
                "repetitions": r.repetitions,
                "rom_min": r.rom_min,
                "rom_max": r.rom_max,
                "rom_average": r.rom_average,
                "performance_score": r.performance_score,
                "feedback": r.feedback,
            }
