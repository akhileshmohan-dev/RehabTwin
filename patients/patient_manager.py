from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PatientManager:
    """
    Manages RehabTwin patient records.

    Each patient gets:
        data/patients/<patient_id>/
            profile.json
            sessions/
    """

    def __init__(self, data_root: str | Path | None = None) -> None:
        project_root = Path(__file__).resolve().parent.parent

        if data_root is None:
            data_root = project_root / "data" / "patients"

        self.data_root = Path(data_root)

        self.data_root.mkdir(
            parents=True,
            exist_ok=True
        )

    # ------------------------------------------------------------------
    # PATIENT ID
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_patient_id(patient_id: str) -> str:
        patient_id = patient_id.strip().upper()

        if not patient_id:
            raise ValueError("Patient ID cannot be empty.")

        if "/" in patient_id or "\\" in patient_id:
            raise ValueError("Invalid patient ID.")

        return patient_id

    # ------------------------------------------------------------------
    # PATHS
    # ------------------------------------------------------------------

    def _patient_directory(self, patient_id: str) -> Path:
        patient_id = self._normalise_patient_id(patient_id)

        return self.data_root / patient_id

    def _profile_path(self, patient_id: str) -> Path:
        return self._patient_directory(patient_id) / "profile.json"

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create_patient(
        self,
        patient_id: str,
        name: str
    ) -> dict[str, Any]:
        patient_id = self._normalise_patient_id(patient_id)
        name = name.strip()

        if not name:
            raise ValueError("Patient name cannot be empty.")

        patient_directory = self._patient_directory(
            patient_id
        )

        if patient_directory.exists():
            raise ValueError(
                f"Patient '{patient_id}' already exists."
            )

        sessions_directory = (
            patient_directory / "sessions"
        )

        sessions_directory.mkdir(
            parents=True,
            exist_ok=False
        )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        profile = {
            "patient_id": patient_id,
            "name": name,
            "created_at": now,
            "updated_at": now
        }

        self._write_profile(
            patient_id,
            profile
        )

        return profile

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_patient(
        self,
        patient_id: str
    ) -> dict[str, Any] | None:
        profile_path = self._profile_path(
            patient_id
        )

        if not profile_path.exists():
            return None

        try:
            with profile_path.open(
                "r",
                encoding="utf-8"
            ) as file:
                return json.load(file)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid patient profile: {profile_path}"
            ) from exc

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    def list_patients(self) -> list[dict[str, Any]]:
        patients: list[dict[str, Any]] = []

        for patient_directory in sorted(
            self.data_root.iterdir()
        ):
            if not patient_directory.is_dir():
                continue

            profile_path = (
                patient_directory / "profile.json"
            )

            if not profile_path.exists():
                continue

            try:
                with profile_path.open(
                    "r",
                    encoding="utf-8"
                ) as file:
                    profile = json.load(file)

                patients.append(profile)

            except json.JSONDecodeError:
                continue

        return patients

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update_patient(
        self,
        patient_id: str,
        **fields: Any
    ) -> dict[str, Any]:
        patient = self.get_patient(
            patient_id
        )

        if patient is None:
            raise ValueError(
                f"Patient '{patient_id}' does not exist."
            )

        protected_fields = {
            "patient_id",
            "created_at"
        }

        for key, value in fields.items():
            if key in protected_fields:
                continue

            patient[key] = value

        patient["updated_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        self._write_profile(
            patient_id,
            patient
        )

        return patient

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete_patient(
        self,
        patient_id: str
    ) -> bool:
        """
        Deletes a patient only when their directory
        contains no session data.
        """

        patient_directory = self._patient_directory(
            patient_id
        )

        if not patient_directory.exists():
            return False

        sessions_directory = (
            patient_directory / "sessions"
        )

        if sessions_directory.exists():
            remaining_files = list(
                sessions_directory.iterdir()
            )

            if remaining_files:
                raise ValueError(
                    f"Patient '{patient_id}' has sessions. "
                    "Delete/archive those sessions first."
                )

        profile_path = (
            patient_directory / "profile.json"
        )

        if profile_path.exists():
            profile_path.unlink()

        if sessions_directory.exists():
            sessions_directory.rmdir()

        patient_directory.rmdir()

        return True

    # ------------------------------------------------------------------
    # INTERNAL WRITE
    # ------------------------------------------------------------------

    def _write_profile(
        self,
        patient_id: str,
        profile: dict[str, Any]
    ) -> None:
        profile_path = self._profile_path(
            patient_id
        )

        profile_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with profile_path.open(
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                profile,
                file,
                indent=4,
                ensure_ascii=False
            )