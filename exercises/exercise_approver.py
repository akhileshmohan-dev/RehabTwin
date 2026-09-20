from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .exercise_config import Exercise, ExerciseConfig


@dataclass(frozen=True)
class ExerciseComparison:
    patient_id: str | None
    session_id: str | None

    exercise_id: str
    exercise_name: str

    target_rom_min_deg: float | None
    target_rom_max_deg: float | None
    target_reps: int | None

    recorded_rom_min_deg: float | None
    recorded_rom_max_deg: float | None
    recorded_rom_average_deg: float | None
    recorded_reps: int | None

    rom_min_error_deg: float | None
    rom_max_error_deg: float | None

    target_rom_span_deg: float | None
    recorded_rom_span_deg: float | None

    rom_coverage_percent: float | None

    rom_range_reached: bool | None
    reps_target_reached: bool | None


class ExerciseApprover:
    """
    Compares therapist/frontend exercise configuration against
    measured values stored in a Digital Thread session export.

    This module only performs a factual configuration-vs-measurement
    comparison.

    It does not:
        - edit exercise configuration
        - edit Digital Thread data
        - calculate pose from raw landmarks
        - make clinical decisions
    """

    def __init__(
        self,
        exercise_config: ExerciseConfig
    ) -> None:
        self.exercise_config = exercise_config

    # -----------------------------------------------------------------
    # DIGITAL THREAD LOADING
    # -----------------------------------------------------------------

    @staticmethod
    def load_thread_session(
        session_path: str | Path
    ) -> dict[str, Any]:

        path = Path(session_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Digital Thread session export not found: {path}"
            )

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                "Digital Thread export must contain a JSON object."
            )

        return data

    # -----------------------------------------------------------------
    # DIGITAL THREAD RESULTS
    # -----------------------------------------------------------------

    @staticmethod
    def _get_results(
        session_data: dict[str, Any]
    ) -> list[dict[str, Any]]:

        results = session_data.get("results")

        if results is None:
            data_section = session_data.get("data")

            if isinstance(data_section, dict):
                results = data_section.get("results")

        if not isinstance(results, list):
            raise ValueError(
                "Digital Thread session does not contain a 'results' list."
            )

        return [
            result
            for result in results
            if isinstance(result, dict)
        ]

    # -----------------------------------------------------------------
    # TEXT NORMALISATION
    # -----------------------------------------------------------------

    @staticmethod
    def _normalise_text(
        value: str
    ) -> str:

        return (
            value.strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

    # -----------------------------------------------------------------
    # RESULT MATCHING
    # -----------------------------------------------------------------

    def _find_result(
        self,
        exercise: Exercise,
        results: list[dict[str, Any]]
    ) -> dict[str, Any]:

        exercise_id = self._normalise_text(
            exercise.exercise_id
        )

        exercise_name = self._normalise_text(
            exercise.exercise_name
        )

        matches: list[dict[str, Any]] = []

        for result in results:

            result_exercise = result.get(
                "exercise"
            )

            if not isinstance(
                result_exercise,
                str
            ):
                continue

            normalised_result = self._normalise_text(
                result_exercise
            )

            if (
                normalised_result == exercise_id
                or
                normalised_result == exercise_name
            ):
                matches.append(
                    result
                )

        if not matches:
            raise ValueError(
                "No Digital Thread result matched exercise "
                f"'{exercise.exercise_id}'. "
                "The stored result exercise must match the "
                "configured exercise ID or exercise name."
            )

        if len(matches) > 1:
            raise ValueError(
                "Multiple Digital Thread results matched exercise "
                f"'{exercise.exercise_id}'."
            )

        return matches[0]

    # -----------------------------------------------------------------
    # SESSION METADATA
    # -----------------------------------------------------------------

    @staticmethod
    def _get_session_metadata(
        session_data: dict[str, Any]
    ) -> tuple[str | None, str | None]:

        session = session_data.get(
            "session"
        )

        if not isinstance(
            session,
            dict
        ):
            return None, None

        patient_id = session.get(
            "patient_id"
        )

        session_id = session.get(
            "session_id"
        )

        return (
            patient_id
            if isinstance(patient_id, str)
            else None,

            session_id
            if isinstance(session_id, str)
            else None
        )

    # -----------------------------------------------------------------
    # VALUE CONVERSION
    # -----------------------------------------------------------------

    @staticmethod
    def _to_float(
        value: Any
    ) -> float | None:

        if value is None:
            return None

        try:
            return float(value)

        except (
            TypeError,
            ValueError
        ):
            return None

    @staticmethod
    def _to_int(
        value: Any
    ) -> int | None:

        if value is None:
            return None

        try:
            return int(value)

        except (
            TypeError,
            ValueError
        ):
            return None

    # -----------------------------------------------------------------
    # COMPARISON
    # -----------------------------------------------------------------

    def compare(
        self,
        exercise_id: str,
        session_path: str | Path
    ) -> ExerciseComparison:

        exercise = (
            self.exercise_config.get_exercise(
                exercise_id
            )
        )

        if exercise is None:
            raise ValueError(
                f"Exercise not found in configuration: "
                f"{exercise_id}"
            )

        session_data = (
            self.load_thread_session(
                session_path
            )
        )

        results = (
            self._get_results(
                session_data
            )
        )

        result = (
            self._find_result(
                exercise,
                results
            )
        )

        patient_id, session_id = (
            self._get_session_metadata(
                session_data
            )
        )

        # -------------------------------------------------------------
        # Recorded values
        # -------------------------------------------------------------

        recorded_rom_min = (
            self._to_float(
                result.get("rom_min")
            )
        )

        recorded_rom_max = (
            self._to_float(
                result.get("rom_max")
            )
        )

        recorded_rom_average = (
            self._to_float(
                result.get("rom_average")
            )
        )

        recorded_reps = (
            self._to_int(
                result.get("repetitions")
            )
        )

        # -------------------------------------------------------------
        # ROM errors
        # -------------------------------------------------------------

        rom_min_error = None

        if (
            exercise.rom_min_deg is not None
            and
            recorded_rom_min is not None
        ):
            rom_min_error = (
                recorded_rom_min
                -
                exercise.rom_min_deg
            )

        rom_max_error = None

        if (
            exercise.rom_max_deg is not None
            and
            recorded_rom_max is not None
        ):
            rom_max_error = (
                recorded_rom_max
                -
                exercise.rom_max_deg
            )

        # -------------------------------------------------------------
        # ROM spans
        # -------------------------------------------------------------

        target_rom_span = None

        if (
            exercise.rom_min_deg is not None
            and
            exercise.rom_max_deg is not None
        ):
            target_rom_span = (
                exercise.rom_max_deg
                -
                exercise.rom_min_deg
            )

        recorded_rom_span = None

        if (
            recorded_rom_min is not None
            and
            recorded_rom_max is not None
        ):
            recorded_rom_span = (
                recorded_rom_max
                -
                recorded_rom_min
            )

        # -------------------------------------------------------------
        # ROM coverage
        # -------------------------------------------------------------

        rom_coverage_percent = None

        if (
            exercise.rom_min_deg is not None
            and
            exercise.rom_max_deg is not None
            and
            recorded_rom_min is not None
            and
            recorded_rom_max is not None
            and
            target_rom_span is not None
            and
            target_rom_span > 0
        ):
            overlap_min = max(
                exercise.rom_min_deg,
                recorded_rom_min
            )

            overlap_max = min(
                exercise.rom_max_deg,
                recorded_rom_max
            )

            overlap = max(
                0.0,
                overlap_max - overlap_min
            )

            rom_coverage_percent = (
                overlap
                /
                target_rom_span
            ) * 100.0

            rom_coverage_percent = min(
                100.0,
                max(
                    0.0,
                    rom_coverage_percent
                )
            )

        # -------------------------------------------------------------
        # ROM range reached
        # -------------------------------------------------------------

        rom_range_reached = None

        if (
            exercise.rom_min_deg is not None
            and
            exercise.rom_max_deg is not None
            and
            recorded_rom_min is not None
            and
            recorded_rom_max is not None
        ):
            rom_range_reached = (
                recorded_rom_min
                <=
                exercise.rom_min_deg
                and
                recorded_rom_max
                >=
                exercise.rom_max_deg
            )

        # -------------------------------------------------------------
        # Repetition target
        # -------------------------------------------------------------

        reps_target_reached = None

        if (
            exercise.target_reps is not None
            and
            recorded_reps is not None
        ):
            reps_target_reached = (
                recorded_reps
                >=
                exercise.target_reps
            )

        return ExerciseComparison(
            patient_id=patient_id,
            session_id=session_id,
            exercise_id=exercise.exercise_id,
            exercise_name=exercise.exercise_name,
            target_rom_min_deg=exercise.rom_min_deg,
            target_rom_max_deg=exercise.rom_max_deg,
            target_reps=exercise.target_reps,
            recorded_rom_min_deg=recorded_rom_min,
            recorded_rom_max_deg=recorded_rom_max,
            recorded_rom_average_deg=recorded_rom_average,
            recorded_reps=recorded_reps,
            rom_min_error_deg=rom_min_error,
            rom_max_error_deg=rom_max_error,
            target_rom_span_deg=target_rom_span,
            recorded_rom_span_deg=recorded_rom_span,
            rom_coverage_percent=rom_coverage_percent,
            rom_range_reached=rom_range_reached,
            reps_target_reached=reps_target_reached,
        )

    # -----------------------------------------------------------------
    # DICTIONARY OUTPUT
    # -----------------------------------------------------------------

    def compare_as_dict(
        self,
        exercise_id: str,
        session_path: str | Path
    ) -> dict[str, Any]:

        comparison = self.compare(
            exercise_id,
            session_path
        )

        return asdict(
            comparison
        )

    # -----------------------------------------------------------------
    # SAVE COMPARISON
    # -----------------------------------------------------------------

    def save_comparison(
        self,
        comparison: ExerciseComparison,
        output_path: str | Path
    ) -> None:

        path = Path(
            output_path
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with path.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                asdict(comparison),
                file,
                indent=4,
                ensure_ascii=False
            )


# ---------------------------------------------------------------------
# COMMAND LINE
# ---------------------------------------------------------------------

def main() -> None:

    if len(sys.argv) < 4:
        print(
            "Usage:\n"
            "  python -m exercises.exercise_approver "
            "<exercise_csv> <exercise_id> "
            "<digital_thread_session.json>"
        )

        sys.exit(1)

    csv_path = Path(
        sys.argv[1]
    )

    exercise_id = sys.argv[2]

    session_path = Path(
        sys.argv[3]
    )

    config = ExerciseConfig(
        csv_path
    )

    approver = ExerciseApprover(
        config
    )

    comparison = approver.compare(
        exercise_id,
        session_path
    )

    print(
        json.dumps(
            asdict(comparison),
            indent=4
        )
    )


if __name__ == "__main__":
    main()