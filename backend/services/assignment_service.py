"""
Assignment service managing therapist exercise assignments for patients.
"""
from typing import List, Optional, Dict, Any

from backend.repositories.interfaces import IAssignmentRepository, IPatientRepository
from backend.schemas.assignment import (
    CreateAssignmentRequest,
    UpdateAssignmentRequest,
    AssignmentResponse,
    AssignmentListResponse,
)
from backend.services.patient_service import (
    PatientNotFoundException,
    PatientNotActiveException,
)
from backend.services.session_service import InvalidSideException
from rehabilitation.exercises import EXERCISE_REGISTRY


class AssignmentNotFoundException(Exception):
    """Raised when an assignment is not found or does not belong to the patient."""
    def __init__(self, assignment_id: int):
        self.assignment_id = assignment_id
        super().__init__(f"Exercise assignment '{assignment_id}' not found.")


class DuplicateAssignmentException(Exception):
    """Raised when an assignment already exists for (patient_id, exercise_id, side)."""
    def __init__(self, message: str):
        super().__init__(message)


class UnknownExerciseException(Exception):
    """Raised when an unknown exercise_id is specified."""
    def __init__(self, exercise_id: str):
        self.exercise_id = exercise_id
        super().__init__(f"Unknown exercise '{exercise_id}'. Must be one of {list(EXERCISE_REGISTRY.keys())}.")


class InvalidTargetException(Exception):
    """Raised when target values are non-positive or invalid."""
    pass


class ExerciseNotAssignedException(Exception):
    """Raised when a patient attempts to start an exercise that has not been assigned to them."""
    pass


class AssignmentService:
    """Service layer orchestrating patient exercise assignments."""

    def __init__(
        self,
        assignment_repo: IAssignmentRepository,
        patient_repo: IPatientRepository,
    ):
        self.assignment_repo = assignment_repo
        self.patient_repo = patient_repo

    def assign_exercise(self, patient_id: str, request: CreateAssignmentRequest) -> AssignmentResponse:
        """Assign an exercise to a patient with targets and side selection."""
        # 1. Verify patient exists
        patient = self.patient_repo.get_patient(patient_id)
        if not patient:
            raise PatientNotFoundException(patient_id)

        # 2. Verify patient is active
        if patient.get("status") == "INACTIVE":
            raise PatientNotActiveException(patient_id)

        # 3. Verify exercise exists
        if request.exercise_id not in EXERCISE_REGISTRY:
            raise UnknownExerciseException(request.exercise_id)

        # 4. Validate side
        side = request.side.strip().lower()
        if side not in ("left", "right"):
            raise InvalidSideException(request.side)

        # 5. Validate targets
        if request.target_rom is not None and request.target_rom <= 0:
            raise InvalidTargetException("target_rom must be greater than 0.")
        if request.target_repetitions is not None and request.target_repetitions <= 0:
            raise InvalidTargetException("target_repetitions must be greater than 0.")
        if request.sessions_per_day is not None and request.sessions_per_day <= 0:
            raise InvalidTargetException("sessions_per_day must be greater than 0.")

        # 6. Check duplicate or reactivation
        existing = self.assignment_repo.get_assignment_by_exercise_and_side(patient_id, request.exercise_id, side)
        if existing:
            if existing.get("active"):
                raise DuplicateAssignmentException(
                    f"Exercise '{request.exercise_id}' ({side}) is already assigned to patient '{patient_id}'."
                )
            # Reactivate inactive assignment with updated configuration
            updated = self.assignment_repo.update_assignment(
                assignment_id=existing["id"],
                updates={
                    "target_rom": request.target_rom,
                    "target_repetitions": request.target_repetitions,
                    "sessions_per_day": request.sessions_per_day,
                    "notes": request.notes or "",
                    "active": True,
                }
            )
            exercise_def = EXERCISE_REGISTRY[request.exercise_id]
            return AssignmentResponse(
                **updated,
                exercise_name=exercise_def.name,
            )

        # 7. Persist assignment
        created = self.assignment_repo.assign_exercise({
            "patient_id": patient_id,
            "exercise_id": request.exercise_id,
            "side": side,
            "target_rom": request.target_rom,
            "target_repetitions": request.target_repetitions,
            "sessions_per_day": request.sessions_per_day,
            "notes": request.notes or "",
            "active": True,
        })
        exercise_def = EXERCISE_REGISTRY[request.exercise_id]
        return AssignmentResponse(
            **created,
            exercise_name=exercise_def.name,
        )

    def list_assignments(self, patient_id: str, active_only: bool = False) -> AssignmentListResponse:
        """List exercise assignments for a specific patient."""
        if not self.patient_repo.patient_exists(patient_id):
            raise PatientNotFoundException(patient_id)

        records = self.assignment_repo.list_assignments(patient_id, active_only=active_only)
        items: List[AssignmentResponse] = []
        for r in records:
            ex_name = EXERCISE_REGISTRY[r["exercise_id"]].name if r["exercise_id"] in EXERCISE_REGISTRY else r["exercise_id"]
            items.append(AssignmentResponse(**r, exercise_name=ex_name))

        return AssignmentListResponse(
            patient_id=patient_id,
            total_assignments=len(items),
            assignments=items,
        )

    def get_assignment(self, patient_id: str, assignment_id: int) -> AssignmentResponse:
        """Retrieve assignment by ID enforcing patient isolation."""
        if not self.patient_repo.patient_exists(patient_id):
            raise PatientNotFoundException(patient_id)

        a = self.assignment_repo.get_assignment(assignment_id)
        if not a or a["patient_id"] != patient_id:
            raise AssignmentNotFoundException(assignment_id)

        ex_name = EXERCISE_REGISTRY[a["exercise_id"]].name if a["exercise_id"] in EXERCISE_REGISTRY else a["exercise_id"]
        return AssignmentResponse(**a, exercise_name=ex_name)

    def update_assignment(
        self, patient_id: str, assignment_id: int, request: UpdateAssignmentRequest
    ) -> AssignmentResponse:
        """Update assignment targets and status enforcing patient isolation."""
        if not self.patient_repo.patient_exists(patient_id):
            raise PatientNotFoundException(patient_id)

        a = self.assignment_repo.get_assignment(assignment_id)
        if not a or a["patient_id"] != patient_id:
            raise AssignmentNotFoundException(assignment_id)

        if request.target_rom is not None and request.target_rom <= 0:
            raise InvalidTargetException("target_rom must be greater than 0.")
        if request.target_repetitions is not None and request.target_repetitions <= 0:
            raise InvalidTargetException("target_repetitions must be greater than 0.")
        if request.sessions_per_day is not None and request.sessions_per_day <= 0:
            raise InvalidTargetException("sessions_per_day must be greater than 0.")

        updates = request.model_dump(exclude_unset=True)
        updated = self.assignment_repo.update_assignment(assignment_id, updates)
        if not updated:
            raise AssignmentNotFoundException(assignment_id)

        ex_name = EXERCISE_REGISTRY[updated["exercise_id"]].name if updated["exercise_id"] in EXERCISE_REGISTRY else updated["exercise_id"]
        return AssignmentResponse(**updated, exercise_name=ex_name)

    def deactivate_assignment(self, patient_id: str, assignment_id: int) -> AssignmentResponse:
        """Soft-deactivate an assignment (active=False) preserving historical session data."""
        if not self.patient_repo.patient_exists(patient_id):
            raise PatientNotFoundException(patient_id)

        a = self.assignment_repo.get_assignment(assignment_id)
        if not a or a["patient_id"] != patient_id:
            raise AssignmentNotFoundException(assignment_id)

        deactivated = self.assignment_repo.deactivate_assignment(assignment_id)
        if not deactivated:
            raise AssignmentNotFoundException(assignment_id)

        ex_name = EXERCISE_REGISTRY[deactivated["exercise_id"]].name if deactivated["exercise_id"] in EXERCISE_REGISTRY else deactivated["exercise_id"]
        return AssignmentResponse(**deactivated, exercise_name=ex_name)
