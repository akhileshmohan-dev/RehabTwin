from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exercises.exercise_approver import ExerciseApprover
from exercises.exercise_config import ExerciseConfig
from rehabilitation.session_analyzer import UnitySessionAnalyzer


class RehabTwinSessionService:
    """
    High-level interface for processing one completed RehabTwin session.

    Flow:

        Unity PoseSession
                ↓
        Session Analyzer
                ↓
        Digital Thread
                ↓
        Exercise Approver
                ↓
        Combined session result

    The frontend can use this service without needing to know
    the internal analysis or Digital Thread implementation.
    """

    def __init__(
        self,
        exercise_csv_path: str | Path
    ) -> None:
        self.exercise_csv_path = Path(
            exercise_csv_path
        )

        self.exercise_config = ExerciseConfig(
            self.exercise_csv_path
        )

        self.analyzer = UnitySessionAnalyzer(
            self.exercise_config
        )

        self.approver = ExerciseApprover(
            self.exercise_config
        )

    # -----------------------------------------------------------------
    # PROCESS SESSION
    # -----------------------------------------------------------------

    def process_session(
        self,
        unity_session_path: str | Path,
        exercise_id: str,
        database_url: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze a Unity session, store the result in Digital Thread,
        then compare the Digital Thread result against the exercise
        configuration.
        """

        unity_session_path = Path(
            unity_session_path
        )

        # -------------------------------------------------------------
        # Validate exercise first
        # -------------------------------------------------------------

        exercise = self.exercise_config.get_exercise(
            exercise_id
        )

        if exercise is None:
            raise ValueError(
                f"Exercise not found in configuration: "
                f"{exercise_id}"
            )

        # -------------------------------------------------------------
        # Analyze Unity session
        # -------------------------------------------------------------

        analysis_result = self.analyzer.analyze(
            exercise_id=exercise_id,
            unity_session_path=unity_session_path,
            database_url=database_url,
        )

        thread_export_path = Path(
            analysis_result["thread_export"]
        )

        if not thread_export_path.is_absolute():
            thread_export_path = (
                Path.cwd() /
                thread_export_path
            )

        if not thread_export_path.exists():
            raise FileNotFoundError(
                "Digital Thread export was not created: "
                f"{thread_export_path}"
            )

        # -------------------------------------------------------------
        # Approve / compare
        # -------------------------------------------------------------

        comparison = self.approver.compare(
            exercise_id=exercise_id,
            session_path=thread_export_path,
        )

        comparison_dict = (
            self.approver.compare_as_dict(
                exercise_id=exercise_id,
                session_path=thread_export_path,
            )
        )

        # -------------------------------------------------------------
        # Save combined service result
        # -------------------------------------------------------------

        session_id = analysis_result[
            "session_id"
        ]

        output_path = (
            thread_export_path.parent /
            f"{session_id}_approval.json"
        )

        combined_result = {
            "session": {
                "session_id": analysis_result[
                    "session_id"
                ],
                "patient_id": analysis_result[
                    "patient_id"
                ],
                "exercise_id": analysis_result[
                    "exercise_id"
                ],
                "exercise_name": analysis_result[
                    "exercise_name"
                ],
                "selected_side": analysis_result[
                    "selected_side"
                ],
            },

            "measured_result": analysis_result[
                "result"
            ],

            "comparison": comparison_dict,

            "digital_thread_export":
                str(thread_export_path),
        }

        output_path.write_text(
            json.dumps(
                combined_result,
                indent=4,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return {
            **combined_result,

            "approval_export":
                str(output_path),
        }


# ---------------------------------------------------------------------
# Simple helper
# ---------------------------------------------------------------------

def process_session(
    unity_session_path: str | Path,
    exercise_id: str,
    exercise_csv_path: str | Path = "exercises/exercises.csv",
    database_url: str | None = None
) -> dict[str, Any]:
    """
    Convenience function for frontend/backend callers.
    """

    service = RehabTwinSessionService(
        exercise_csv_path
    )

    return service.process_session(
        unity_session_path=unity_session_path,
        exercise_id=exercise_id,
        database_url=database_url,
    )