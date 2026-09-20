from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Exercise:
    """
    One exercise definition imported from a therapist/frontend CSV.
    """

    exercise_id: str
    exercise_name: str

    target_joint: str
    side: str

    rom_min_deg: float | None
    rom_max_deg: float | None

    target_reps: int | None

    extra: dict[str, Any] = field(
        default_factory=dict
    )


class ExerciseConfig:
    """
    Pure exercise CSV importer.

    Responsibilities:
        - Read the CSV.
        - Validate required information.
        - Convert values to appropriate types.
        - Expose exercise definitions.

    It does not:
        - Edit the CSV.
        - Create exercises.
        - Calculate patient performance.
        - Modify Digital Thread data.

    Supported ROM column aliases:
        rom_min_deg / min_angle
        rom_max_deg / max_angle
    """

    COLUMN_ALIASES = {
        "rom_min_deg": (
            "rom_min_deg",
            "min_angle",
        ),
        "rom_max_deg": (
            "rom_max_deg",
            "max_angle",
        ),
    }

    REQUIRED_COLUMNS = {
        "exercise_id",
        "exercise_name",
        "target_joint",
        "side",
        "target_reps",
    }

    def __init__(
        self,
        csv_path: str | Path
    ) -> None:
        self.csv_path = Path(csv_path)

        self.exercises: list[Exercise] = []

        self._load()

    # ------------------------------------------------------------------
    # LOAD
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Exercise CSV not found: {self.csv_path}"
            )

        with self.csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise ValueError(
                    "Exercise CSV has no header."
                )

            columns = {
                column.strip()
                for column in reader.fieldnames
                if column is not None
            }

            missing = (
                self.REQUIRED_COLUMNS - columns
            )

            if missing:
                raise ValueError(
                    "Exercise CSV is missing required "
                    "columns: "
                    + ", ".join(
                        sorted(missing)
                    )
                )

            for row_number, row in enumerate(
                reader,
                start=2
            ):
                self.exercises.append(
                    self._parse_row(
                        row,
                        row_number
                    )
                )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _required_text(
        row: dict[str, str],
        key: str,
        row_number: int
    ) -> str:
        value = (
            row.get(key, "")
            or ""
        ).strip()

        if not value:
            raise ValueError(
                f"Row {row_number}: "
                f"'{key}' cannot be empty."
            )

        return value

    @classmethod
    def _find_alias(
        cls,
        row: dict[str, str],
        canonical_name: str
    ) -> str | None:
        aliases = cls.COLUMN_ALIASES.get(
            canonical_name,
            (canonical_name,)
        )

        for alias in aliases:
            if alias in row:
                return alias

        return None

    @classmethod
    def _optional_float(
        cls,
        row: dict[str, str],
        canonical_name: str,
        row_number: int
    ) -> float | None:
        column = cls._find_alias(
            row,
            canonical_name
        )

        if column is None:
            return None

        value = (
            row.get(column, "")
            or ""
        ).strip()

        if not value:
            return None

        try:
            return float(value)

        except ValueError as exc:
            raise ValueError(
                f"Row {row_number}: "
                f"'{column}' must be numeric."
            ) from exc

    @staticmethod
    def _optional_int(
        row: dict[str, str],
        key: str,
        row_number: int
    ) -> int | None:
        value = (
            row.get(key, "")
            or ""
        ).strip()

        if not value:
            return None

        try:
            return int(value)

        except ValueError as exc:
            raise ValueError(
                f"Row {row_number}: "
                f"'{key}' must be an integer."
            ) from exc

    # ------------------------------------------------------------------
    # PARSE
    # ------------------------------------------------------------------

    @classmethod
    def _parse_row(
        cls,
        row: dict[str, str],
        row_number: int
    ) -> Exercise:

        exercise_id = cls._required_text(
            row,
            "exercise_id",
            row_number
        )

        exercise_name = cls._required_text(
            row,
            "exercise_name",
            row_number
        )

        target_joint = cls._required_text(
            row,
            "target_joint",
            row_number
        ).lower()

        side = cls._required_text(
            row,
            "side",
            row_number
        ).lower()

        rom_min_deg = cls._optional_float(
            row,
            "rom_min_deg",
            row_number
        )

        rom_max_deg = cls._optional_float(
            row,
            "rom_max_deg",
            row_number
        )

        target_reps = cls._optional_int(
            row,
            "target_reps",
            row_number
        )

        if (
            rom_min_deg is not None
            and rom_max_deg is not None
            and rom_min_deg > rom_max_deg
        ):
            raise ValueError(
                f"Row {row_number}: "
                "ROM minimum cannot be greater "
                "than ROM maximum."
            )

        if (
            target_reps is not None
            and target_reps < 0
        ):
            raise ValueError(
                f"Row {row_number}: "
                "target_reps cannot be negative."
            )

        known_columns = {
            "exercise_id",
            "exercise_name",
            "target_joint",
            "side",
            "rom_min_deg",
            "rom_max_deg",
            "min_angle",
            "max_angle",
            "target_reps",
        }

        extra = {
            key: value
            for key, value in row.items()
            if key not in known_columns
        }

        return Exercise(
            exercise_id=exercise_id,
            exercise_name=exercise_name,
            target_joint=target_joint,
            side=side,
            rom_min_deg=rom_min_deg,
            rom_max_deg=rom_max_deg,
            target_reps=target_reps,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # ACCESS
    # ------------------------------------------------------------------

    def get_exercises(
        self
    ) -> list[Exercise]:
        return list(
            self.exercises
        )

    def get_exercise(
        self,
        exercise_id: str
    ) -> Exercise | None:
        exercise_id = exercise_id.strip()

        for exercise in self.exercises:
            if exercise.exercise_id == exercise_id:
                return exercise

        return None

    def __len__(self) -> int:
        return len(
            self.exercises
        )