from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from digital_thread import DigitalThread
from exercises.exercise_config import ExerciseConfig
from pose_estimation.angle_utils import calculate_angle
from rehabilitation.data_filter import get_valid_angle
from rehabilitation.repetition_counter import RepetitionCounter
from rehabilitation.rom_calculator import calculate_rom
from rehabilitation.smoothing import MovingAverageFilter


ANGLE_LANDMARKS = {
    "left_elbow": (
        "LEFT_SHOULDER",
        "LEFT_ELBOW",
        "LEFT_WRIST",
    ),
    "right_elbow": (
        "RIGHT_SHOULDER",
        "RIGHT_ELBOW",
        "RIGHT_WRIST",
    ),
    "left_shoulder": (
        "LEFT_HIP",
        "LEFT_SHOULDER",
        "LEFT_ELBOW",
    ),
    "right_shoulder": (
        "RIGHT_HIP",
        "RIGHT_SHOULDER",
        "RIGHT_ELBOW",
    ),
}


class UnitySessionAnalyzer:
    """
    Analyzes an already-recorded Unity PoseSession and stores
    the analyzed frames and final result in the Digital Thread.

    Flow:

        Unity PoseSession JSON
                ↓
        angle calculation
                ↓
        smoothing
                ↓
        repetition counter
                ↓
        ROM calculation
                ↓
        Digital Thread
    """

    def __init__(
        self,
        exercise_config: ExerciseConfig
    ) -> None:
        self.exercise_config = exercise_config

    # -----------------------------------------------------------------
    # LOAD UNITY SESSION
    # -----------------------------------------------------------------

    @staticmethod
    def load_unity_session(
        path: str | Path
    ) -> dict[str, Any]:

        session_path = Path(path)

        if not session_path.exists():
            raise FileNotFoundError(
                f"Unity session not found: {session_path}"
            )

        with session_path.open(
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                "Unity session must contain a JSON object."
            )

        if not data.get("sessionId"):
            raise ValueError(
                "Unity session is missing sessionId."
            )

        if not data.get("patientId"):
            raise ValueError(
                "Unity session is missing patientId."
            )

        frames = data.get("frames")

        if not isinstance(frames, list):
            raise ValueError(
                "Unity session has no valid frames list."
            )

        if not frames:
            raise ValueError(
                "Unity session contains no frames."
            )

        return data

    # -----------------------------------------------------------------
    # LANDMARK CONVERSION
    # -----------------------------------------------------------------

    @staticmethod
    def _landmark_dict(
        pose: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:

        landmarks = pose.get("landmarks")

        if not isinstance(landmarks, list):
            return {}

        output: dict[str, dict[str, Any]] = {}

        for landmark in landmarks:
            if not isinstance(landmark, dict):
                continue

            name = landmark.get("name")

            if not isinstance(name, str):
                continue

            if not name:
                continue

            output[name] = landmark

        return output

    # -----------------------------------------------------------------
    # ANGLES
    # -----------------------------------------------------------------

    @staticmethod
    def _calculate_angles(
        landmarks: dict[str, dict[str, Any]]
    ) -> dict[str, float | None]:

        angles: dict[str, float | None] = {}

        for angle_name, names in ANGLE_LANDMARKS.items():

            points = [
                landmarks.get(name)
                for name in names
            ]

            if any(
                point is None
                for point in points
            ):
                angles[angle_name] = None
                continue

            try:
                angles[angle_name] = calculate_angle(
                    points[0],
                    points[1],
                    points[2]
                )

            except (
                KeyError,
                TypeError,
                ValueError,
                ZeroDivisionError
            ):
                angles[angle_name] = None

        return angles

    # -----------------------------------------------------------------
    # VISIBILITY
    # -----------------------------------------------------------------

    @staticmethod
    def _visibility_map(
        landmarks: dict[str, dict[str, Any]]
    ) -> dict[str, float]:

        visibility: dict[str, float] = {}

        for name, landmark in landmarks.items():
            try:
                visibility[name] = float(
                    landmark.get(
                        "visibility",
                        0.0
                    )
                )
            except (
                TypeError,
                ValueError
            ):
                visibility[name] = 0.0

        return visibility

    # -----------------------------------------------------------------
    # ANGLE NAME
    # -----------------------------------------------------------------

    @staticmethod
    def _angle_name(
        target_joint: str,
        side: str
    ) -> str:

        return (
            f"{side}_{target_joint}"
        )

    # -----------------------------------------------------------------
    # REPETITION THRESHOLDS
    # -----------------------------------------------------------------

    @staticmethod
    def _thresholds(
        exercise: Any
    ) -> tuple[float, float]:

        extra = exercise.extra or {}

        def get_extra_float(
            *names: str,
            default: float
        ) -> float:

            for name in names:

                value = extra.get(name)

                if (
                    value is None
                    or str(value).strip() == ""
                ):
                    continue

                try:
                    return float(value)

                except ValueError:
                    continue

            return default

        flexed_threshold = get_extra_float(
            "flexed_threshold",
            "flexion_threshold",
            default=100.0
        )

        extended_threshold = get_extra_float(
            "extended_threshold",
            "extension_threshold",
            default=160.0
        )

        if (
            flexed_threshold >=
            extended_threshold
        ):
            raise ValueError(
                "flexed_threshold must be smaller "
                "than extended_threshold."
            )

        return (
            flexed_threshold,
            extended_threshold,
        )

    # -----------------------------------------------------------------
    # ANALYZE
    # -----------------------------------------------------------------

    def analyze(
        self,
        exercise_id: str,
        unity_session_path: str | Path,
        database_url: str | None = None,
        export_path: str | Path | None = None,
    ) -> dict[str, Any]:

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
            self.load_unity_session(
                unity_session_path
            )
        )

        patient_id = str(
            session_data["patientId"]
        )

        unity_session_id = str(
            session_data["sessionId"]
        )

        target_joint = (
            exercise.target_joint
            .strip()
            .lower()
        )

        side = (
            exercise.side
            .strip()
            .lower()
        )

        if target_joint not in {
            "elbow",
            "shoulder",
        }:
            raise ValueError(
                f"Unsupported target joint: "
                f"{exercise.target_joint}"
            )

        if side not in {
            "left",
            "right",
            "both",
        }:
            raise ValueError(
                f"Unsupported exercise side: "
                f"{exercise.side}"
            )

        sides = (
            ["left", "right"]
            if side == "both"
            else [side]
        )

        pipelines: dict[str, dict[str, Any]] = {}

        for current_side in sides:

            flexed_threshold, extended_threshold = (
                self._thresholds(exercise)
            )

            pipelines[current_side] = {
                "smoother":
                    MovingAverageFilter(
                        window_size=5
                    ),

                "counter":
                    RepetitionCounter(
                        flexed_threshold=
                            flexed_threshold,
                        extended_threshold=
                            extended_threshold,
                    ),

                "angles": [],
            }

        # -------------------------------------------------------------
        # Start Digital Thread session
        # -------------------------------------------------------------

        thread = DigitalThread(
            database_url
        )

        thread.start_session(
            patient_id=patient_id,
            exercise=exercise.exercise_id,
            session_id=unity_session_id,
        )

        # -------------------------------------------------------------
        # Process every Unity frame
        # -------------------------------------------------------------

        for frame_index, frame in enumerate(
            session_data["frames"]
        ):

            if not isinstance(frame, dict):
                continue

            pose = frame.get("pose")

            if not isinstance(pose, dict):
                continue

            landmarks = self._landmark_dict(
                pose
            )

            if not landmarks:
                continue

            angles = self._calculate_angles(
                landmarks
            )

            visibility = self._visibility_map(
                landmarks
            )

            frame_joint_angles: dict[
                str,
                float
            ] = {}

            frame_phases: list[str] = []

            # ---------------------------------------------------------
            # Analyze selected sides
            # ---------------------------------------------------------

            for current_side in sides:

                angle_name = self._angle_name(
                    target_joint,
                    current_side
                )

                pose_for_filter = {
                    "angles": angles,
                    "visibility": visibility,
                }

                valid_angle = get_valid_angle(
                    pose_for_filter,
                    angle_name
                )

                pipeline = pipelines[
                    current_side
                ]

                smoothed = (
                    pipeline["smoother"]
                    .update(valid_angle)
                )

                if smoothed is not None:

                    pipeline["angles"].append(
                        smoothed
                    )

                    counter_result = (
                        pipeline["counter"]
                        .update(smoothed)
                    )

                    frame_phases.append(
                        counter_result["state"]
                    )

                    frame_joint_angles[
                        angle_name
                    ] = smoothed

            # ---------------------------------------------------------
            # Store analyzed frame
            # ---------------------------------------------------------

            thread.record_frame(
                frame_id=frame_index,
                landmarks=landmarks,
                joint_angles=frame_joint_angles,
                phase=(
                    frame_phases[0]
                    if frame_phases
                    else None
                ),
            )

        # -------------------------------------------------------------
        # Final results
        # -------------------------------------------------------------

        results: dict[
            str,
            dict[str, Any]
        ] = {}

        for current_side, pipeline in (
            pipelines.items()
        ):

            rom = calculate_rom(
                pipeline["angles"]
            )

            angles = pipeline["angles"]

            average_rom = (
                sum(angles) / len(angles)
                if angles
                else None
            )

            results[current_side] = {
                "side":
                    current_side.upper(),

                "repetitions":
                    pipeline["counter"]
                    .repetitions,

                "rom_min":
                    rom["min_angle"],

                "rom_max":
                    rom["max_angle"],

                "rom_average":
                    average_rom,

                "rom":
                    rom["rom"],
            }

        # -------------------------------------------------------------
        # Choose result for the configured exercise
        # -------------------------------------------------------------

        selected_side = max(
            results,
            key=lambda current_side:
                results[current_side]["repetitions"]
        )

        selected_result = results[
            selected_side
        ]

        feedback = (
            f"{selected_side.upper()} side analyzed "
            f"from Unity session. "
            f"Completed "
            f"{selected_result['repetitions']} "
            f"repetitions."
        )

        # -------------------------------------------------------------
        # Store result in Digital Thread
        # -------------------------------------------------------------

        thread.record_result(
            repetitions=
                selected_result[
                    "repetitions"
                ],

            rom_min=
                selected_result[
                    "rom_min"
                ],

            rom_max=
                selected_result[
                    "rom_max"
                ],

            rom_average=
                selected_result[
                    "rom_average"
                ],

            performance_score=None,

            feedback=feedback,
        )

        thread.end_session()

        # -------------------------------------------------------------
        # Export Digital Thread session
        # -------------------------------------------------------------

        if export_path is None:
            export_path = (
                Path("data")
                / "exports"
                / f"{unity_session_id}.json"
            )

        export_path = Path(
            export_path
        )

        exporter = DigitalThread(
            database_url
        )

        exporter.export_session(
            unity_session_id,
            str(export_path)
        )

        return {
            "session_id":
                unity_session_id,

            "patient_id":
                patient_id,

            "exercise_id":
                exercise.exercise_id,

            "exercise_name":
                exercise.exercise_name,

            "selected_side":
                selected_side.upper(),

            "result":
                selected_result,

            "thread_export":
                str(export_path),
        }


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main() -> None:

    if len(sys.argv) < 3:

        print(
            "Usage:\n"
            "  python -m rehabilitation.session_analyzer "
            "<unity_session.json> "
            "<exercise_id> "
            "[exercise_csv]"
        )

        sys.exit(1)

    unity_session_path = Path(
        sys.argv[1]
    )

    exercise_id = sys.argv[2]

    exercise_csv = Path(
        sys.argv[3]
        if len(sys.argv) >= 4
        else "exercises/exercises.csv"
    )

    config = ExerciseConfig(
        exercise_csv
    )

    analyzer = UnitySessionAnalyzer(
        config
    )

    result = analyzer.analyze(
        exercise_id=exercise_id,
        unity_session_path=
            unity_session_path,
    )

    print(
        json.dumps(
            result,
            indent=4
        )
    )


if __name__ == "__main__":
    main()