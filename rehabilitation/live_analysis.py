import csv
import os
import sys
import argparse

import cv2
import mediapipe as mp

from mediapipe.python.solutions import pose as mp_pose
from mediapipe.python.solutions import drawing_utils as mp_drawing


# ---------------------------------------------------------------------
# Repository root
# ---------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(__file__)
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(
        0,
        PROJECT_ROOT
    )


# ---------------------------------------------------------------------
# Allow imports from pose_estimation/
# ---------------------------------------------------------------------

POSE_DIR = os.path.join(
    PROJECT_ROOT,
    "pose_estimation"
)

if POSE_DIR not in sys.path:
    sys.path.insert(
        0,
        POSE_DIR
    )


# ---------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------

from landmark_extractor import extract_landmarks
from angle_utils import calculate_angle
from pose_output import create_pose_frame

from rehabilitation.analysis_pipeline import (
    ElbowAnalysisPipeline
)

from rehabilitation.pose_validator import (
    PoseValidator
)

from digital_thread import DigitalThread

from rehabilitation.unity_bridge import (
    send_pose
)


# ---------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------

OUTPUT_FILE = os.path.join(
    os.path.dirname(__file__),
    "elbow_motion.csv"
)

WINDOW_NAME = (
    "RehabTwin - ROM Tracking"
)


# ---------------------------------------------------------------------
# Display configuration
# ---------------------------------------------------------------------

PANEL_WIDTH = 360

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 800


# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def calculate_elbow_angles(
    landmarks
):
    """
    Calculate elbow angles for both arms.
    """

    angles = {
        "left_elbow": None,
        "right_elbow": None
    }

    # -------------------------------------------------------------
    # Left arm
    # -------------------------------------------------------------

    left_shoulder = landmarks.get(
        "LEFT_SHOULDER"
    )

    left_elbow = landmarks.get(
        "LEFT_ELBOW"
    )

    left_wrist = landmarks.get(
        "LEFT_WRIST"
    )

    if (
        left_shoulder
        and left_elbow
        and left_wrist
    ):

        angles["left_elbow"] = (
            calculate_angle(
                left_shoulder,
                left_elbow,
                left_wrist
            )
        )

    # -------------------------------------------------------------
    # Right arm
    # -------------------------------------------------------------

    right_shoulder = landmarks.get(
        "RIGHT_SHOULDER"
    )

    right_elbow = landmarks.get(
        "RIGHT_ELBOW"
    )

    right_wrist = landmarks.get(
        "RIGHT_WRIST"
    )

    if (
        right_shoulder
        and right_elbow
        and right_wrist
    ):

        angles["right_elbow"] = (
            calculate_angle(
                right_shoulder,
                right_elbow,
                right_wrist
            )
        )

    return angles


def get_rom(
    pipeline
):
    """
    Safely retrieve the current ROM from
    the analysis pipeline.
    """

    rom = pipeline.process(
        None
    )["rom"]

    return rom


def draw_text(
    frame,
    text,
    position,
    scale=0.65,
    thickness=2,
    color=(230, 230, 230)
):
    """
    Draw readable text.
    """

    cv2.putText(
        frame,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA
    )


def format_value(
    value,
    suffix=""
):
    """
    Format numeric values for the debug panel.
    """

    if value is None:
        return "--"

    try:

        return (
            f"{float(value):.1f}"
            f"{suffix}"
        )

    except (
        TypeError,
        ValueError
    ):

        return "--"


# ---------------------------------------------------------------------
# Camera feed fitting
# ---------------------------------------------------------------------

def fit_camera_frame(
    frame,
    target_width,
    target_height
):
    """
    Resize the camera image while preserving its aspect ratio.

    The remaining space is filled with black borders instead of
    stretching or cropping the person.

    This is important because the full body should remain visible.
    """

    source_height, source_width = (
        frame.shape[:2]
    )

    if (
        source_width <= 0
        or source_height <= 0
    ):

        return frame

    scale = min(
        target_width / source_width,
        target_height / source_height
    )

    new_width = max(
        1,
        int(source_width * scale)
    )

    new_height = max(
        1,
        int(source_height * scale)
    )

    resized = cv2.resize(
        frame,
        (
            new_width,
            new_height
        ),
        interpolation=cv2.INTER_AREA
    )

    canvas = (
        __import__("numpy")
        .zeros(
            (
                target_height,
                target_width,
                3
            ),
            dtype=frame.dtype
        )
    )

    x_offset = (
        target_width - new_width
    ) // 2

    y_offset = (
        target_height - new_height
    ) // 2

    canvas[
        y_offset:
        y_offset + new_height,

        x_offset:
        x_offset + new_width
    ] = resized

    return canvas


# ---------------------------------------------------------------------
# Debug side panel
# ---------------------------------------------------------------------

def draw_debug_panel(
    panel,
    validation,
    left_angle,
    right_angle,
    left_rom,
    right_rom,
    frame_id
):
    """
    Draw the dedicated debugging / ROM panel.

    Only ROM and information useful for diagnosing tracking
    are shown.
    """

    panel_height, panel_width = (
        panel.shape[:2]
    )

    # -------------------------------------------------------------
    # Background
    # -------------------------------------------------------------

    panel[:] = (
        25,
        25,
        25
    )

    # -------------------------------------------------------------
    # Title
    # -------------------------------------------------------------

    draw_text(
        panel,
        "REHABTWIN",
        (
            25,
            40
        ),
        scale=0.85,
        thickness=2,
        color=(255, 255, 255)
    )

    draw_text(
        panel,
        "ROM / TRACKING DEBUG",
        (
            25,
            70
        ),
        scale=0.55,
        thickness=1,
        color=(170, 170, 170)
    )

    # -------------------------------------------------------------
    # Tracking section
    # -------------------------------------------------------------

    y = 110

    draw_text(
        panel,
        "TRACKING",
        (
            25,
            y
        ),
        scale=0.65,
        thickness=2
    )

    y += 35

    # State color
    if validation.state == "TRACKING":

        state_color = (
            0,
            255,
            0
        )

    elif validation.state == "HOLDING":

        state_color = (
            0,
            210,
            255
        )

    elif validation.state == "LOST":

        state_color = (
            0,
            0,
            255
        )

    else:

        state_color = (
            255,
            200,
            0
        )

    draw_text(
        panel,
        f"State: {validation.state}",
        (
            25,
            y
        ),
        scale=0.58,
        color=state_color
    )

    y += 30

    draw_text(
        panel,
        (
            f"Landmarks: "
            f"{validation.landmark_count}/33"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"Visible: "
            f"{validation.visible_count}/33"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"Valid streak: "
            f"{validation.consecutive_valid_frames}/5"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"Invalid streak: "
            f"{validation.consecutive_invalid_frames}/10"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"Accepted: "
            f"{validation.should_accept}"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    # -------------------------------------------------------------
    # Left arm ROM
    # -------------------------------------------------------------

    y += 45

    draw_text(
        panel,
        "LEFT ARM",
        (
            25,
            y
        ),
        scale=0.65,
        thickness=2
    )

    y += 35

    draw_text(
        panel,
        (
            f"Angle: "
            f"{format_value(left_angle, ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"ROM: "
            f"{format_value(left_rom.get('rom'), ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.62,
        thickness=2
    )

    y += 28

    draw_text(
        panel,
        (
            f"Min: "
            f"{format_value(left_rom.get('min_angle'), ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"Max: "
            f"{format_value(left_rom.get('max_angle'), ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    # -------------------------------------------------------------
    # Right arm ROM
    # -------------------------------------------------------------

    y += 45

    draw_text(
        panel,
        "RIGHT ARM",
        (
            25,
            y
        ),
        scale=0.65,
        thickness=2
    )

    y += 35

    draw_text(
        panel,
        (
            f"Angle: "
            f"{format_value(right_angle, ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"ROM: "
            f"{format_value(right_rom.get('rom'), ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.62,
        thickness=2
    )

    y += 28

    draw_text(
        panel,
        (
            f"Min: "
            f"{format_value(right_rom.get('min_angle'), ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    y += 28

    draw_text(
        panel,
        (
            f"Max: "
            f"{format_value(right_rom.get('max_angle'), ' deg')}"
        ),
        (
            25,
            y
        ),
        scale=0.55
    )

    # -------------------------------------------------------------
    # Frame / reason
    # -------------------------------------------------------------

    y = panel_height - 70

    draw_text(
        panel,
        f"Frame: {frame_id}",
        (
            25,
            y
        ),
        scale=0.5,
        color=(160, 160, 160)
    )

    y += 25

    draw_text(
        panel,
        (
            f"Reason: "
            f"{validation.reason}"
        ),
        (
            25,
            y
        ),
        scale=0.5,
        color=(160, 160, 160)
    )


# ---------------------------------------------------------------------
# Command-line arguments
# ---------------------------------------------------------------------

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "RehabTwin ROM tracking with "
            "full-body camera preview"
        )
    )

    parser.add_argument(
        "--patient-id",
        default="P001",
        help="Patient identifier"
    )

    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "SQLAlchemy DB URL; "
            "defaults to local SQLite"
        )
    )

    parser.add_argument(
        "--export-dir",
        default=os.path.join(
            PROJECT_ROOT,
            "data",
            "exports"
        ),
        help=(
            "Directory for session JSON exports"
        )
    )

    return parser.parse_args()


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    args = parse_args()

    # -------------------------------------------------------------
    # MediaPipe
    # -------------------------------------------------------------

    pose = mp_pose.Pose(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # -------------------------------------------------------------
    # Validator
    # -------------------------------------------------------------

    pose_validator = PoseValidator(
        min_visibility=0.5,
        required_stable_frames=5,
        max_invalid_frames=10
    )

    # -------------------------------------------------------------
    # Camera
    # -------------------------------------------------------------

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():

        raise RuntimeError(
            "Could not open the webcam. "
            "Check that your camera is connected "
            "and not being used by another application."
        )

    # -------------------------------------------------------------
    # Try to request a sensible camera resolution.
    #
    # This does NOT crop the image.
    # fit_camera_frame() preserves the aspect ratio.
    # -------------------------------------------------------------

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        1280
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        720
    )

    # -------------------------------------------------------------
    # Analysis pipelines
    # -------------------------------------------------------------

    left_pipeline = ElbowAnalysisPipeline(
        smoothing_window=5,
        flexed_threshold=100,
        extended_threshold=160
    )

    right_pipeline = ElbowAnalysisPipeline(
        smoothing_window=5,
        flexed_threshold=100,
        extended_threshold=160
    )

    # -------------------------------------------------------------
    # Digital Thread
    # -------------------------------------------------------------

    thread = DigitalThread(
        args.database_url
    )

    session_id = thread.start_session(
        patient_id=args.patient_id,
        exercise="elbow_flexion"
    )

    print()
    print(
        "=============================================="
    )
    print(
        "          REHABTWIN ROM TRACKING"
    )
    print(
        "=============================================="
    )
    print(
        f"Patient: {args.patient_id}"
    )
    print(
        f"Session: {session_id}"
    )
    print()
    print(
        "Waiting for a complete 33-landmark pose."
    )
    print(
        "Press Q to stop."
    )
    print(
        "=============================================="
    )

    # -------------------------------------------------------------
    # CSV
    # -------------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        newline=""
    ) as csv_file:

        writer = csv.writer(
            csv_file
        )

        writer.writerow([
            "timestamp",

            "left_elbow_angle",
            "left_rom_min",
            "left_rom_max",
            "left_rom",

            "right_elbow_angle",
            "right_rom_min",
            "right_rom_max",
            "right_rom",

            "tracking_state",
            "landmarks",
            "visible",
            "accepted"
        ])

        # ---------------------------------------------------------
        # Accepted rehabilitation frame counter
        # ---------------------------------------------------------

        frame_id = 0

        export_path = None

        try:

            while cap.isOpened():

                # =================================================
                # READ CAMERA
                # =================================================

                ret, frame = cap.read()

                if not ret:

                    print(
                        "Failed to read frame from webcam."
                    )

                    break

                # =================================================
                # MEDIA PIPE
                # =================================================

                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB
                )

                results = pose.process(
                    rgb_frame
                )

                # =================================================
                # VALIDATION
                # =================================================

                validation = (
                    pose_validator.validate(
                        results
                    )
                )

                # =================================================
                # DRAW SKELETON
                # =================================================

                if results.pose_landmarks:

                    mp_drawing.draw_landmarks(
                        frame,
                        results.pose_landmarks,
                        mp_pose.POSE_CONNECTIONS
                    )

                # =================================================
                # INVALID / HOLDING
                # =================================================

                if not validation.should_accept:

                    # -------------------------------------------------
                    # We do NOT send invalid data to Unity.
                    # We do NOT update ROM.
                    # -------------------------------------------------

                    left_rom = get_rom(
                        left_pipeline
                    )

                    right_rom = get_rom(
                        right_pipeline
                    )

                    # Create an empty metric state.
                    left_angle = None
                    right_angle = None

                else:

                    # =================================================
                    # VALID TRACKING FRAME
                    # =================================================

                    height, width = (
                        frame.shape[:2]
                    )

                    landmarks = (
                        extract_landmarks(
                            results,
                            width,
                            height
                        )
                    )

                    if not landmarks:

                        left_rom = get_rom(
                            left_pipeline
                        )

                        right_rom = get_rom(
                            right_pipeline
                        )

                        left_angle = None
                        right_angle = None

                    else:

                        # -------------------------------------------------
                        # SEND VALID POSE TO UNITY
                        # -------------------------------------------------

                        send_pose(
                            landmarks
                        )

                        # -------------------------------------------------
                        # Calculate elbow angles
                        # -------------------------------------------------

                        angles = (
                            calculate_elbow_angles(
                                landmarks
                            )
                        )

                        left_angle = (
                            angles[
                                "left_elbow"
                            ]
                        )

                        right_angle = (
                            angles[
                                "right_elbow"
                            ]
                        )

                        # -------------------------------------------------
                        # Analysis frames
                        # -------------------------------------------------

                        left_pose_frame = (
                            create_pose_frame(
                                landmarks,
                                {
                                    "left_elbow":
                                        left_angle
                                }
                            )
                        )

                        right_pose_frame = (
                            create_pose_frame(
                                landmarks,
                                {
                                    "left_elbow":
                                        right_angle
                                }
                            )
                        )

                        # -------------------------------------------------
                        # LEFT ROM
                        # -------------------------------------------------

                        if (
                            left_pose_frame
                            is not None
                        ):

                            left_result = (
                                left_pipeline.process(
                                    left_pose_frame
                                )
                            )

                        else:

                            left_result = (
                                left_pipeline.process(
                                    None
                                )
                            )

                        # -------------------------------------------------
                        # RIGHT ROM
                        # -------------------------------------------------

                        if (
                            right_pose_frame
                            is not None
                        ):

                            right_result = (
                                right_pipeline.process(
                                    right_pose_frame
                                )
                            )

                        else:

                            right_result = (
                                right_pipeline.process(
                                    None
                                )
                            )

                        left_rom = (
                            left_result["rom"]
                        )

                        right_rom = (
                            right_result["rom"]
                        )

                        # -------------------------------------------------
                        # CSV
                        # -------------------------------------------------

                        timestamp = (
                            left_pose_frame[
                                "timestamp"
                            ]
                            if left_pose_frame
                            is not None
                            else 0
                        )

                        writer.writerow([
                            timestamp,

                            left_angle,

                            left_rom[
                                "min_angle"
                            ],

                            left_rom[
                                "max_angle"
                            ],

                            left_rom[
                                "rom"
                            ],

                            right_angle,

                            right_rom[
                                "min_angle"
                            ],

                            right_rom[
                                "max_angle"
                            ],

                            right_rom[
                                "rom"
                            ],

                            validation.state,

                            validation.landmark_count,

                            validation.visible_count,

                            validation.should_accept
                        ])

                        # -------------------------------------------------
                        # Digital Thread
                        #
                        # Kept for now because its current schema is
                        # still being migrated separately.
                        # -------------------------------------------------

                        thread.record_frame(
                            frame_id=frame_id,

                            landmarks=(
                                left_pose_frame[
                                    "landmarks"
                                ]
                                if left_pose_frame
                                is not None
                                else {}
                            ),

                            joint_angles={
                                "left_elbow_raw":
                                    left_angle,

                                "left_elbow_smoothed":
                                    left_result[
                                        "smoothed_angle"
                                    ],

                                "right_elbow_raw":
                                    right_angle,

                                "right_elbow_smoothed":
                                    right_result[
                                        "smoothed_angle"
                                    ]
                            },

                            phase="ROM_TRACKING"
                        )

                        frame_id += 1

                # =================================================
                # CREATE CAMERA VIEW
                # =================================================

                camera_width = (
                    WINDOW_WIDTH
                    - PANEL_WIDTH
                )

                camera_height = (
                    WINDOW_HEIGHT
                )

                camera_view = (
                    fit_camera_frame(
                        frame,
                        camera_width,
                        camera_height
                    )
                )

                # =================================================
                # DEBUG PANEL
                # =================================================

                debug_panel = (
                    __import__("numpy")
                    .zeros(
                        (
                            WINDOW_HEIGHT,
                            PANEL_WIDTH,
                            3
                        ),
                        dtype=frame.dtype
                    )
                )

                draw_debug_panel(
                    debug_panel,
                    validation,
                    left_angle,
                    right_angle,
                    left_rom,
                    right_rom,
                    frame_id
                )

                # =================================================
                # COMBINE CAMERA + PANEL
                # =================================================

                combined = cv2.hconcat([
                    camera_view,
                    debug_panel
                ])

                # =================================================
                # SHOW
                # =================================================

                cv2.imshow(
                    WINDOW_NAME,
                    combined
                )

                # =================================================
                # QUIT
                # =================================================

                if (
                    cv2.waitKey(1) & 0xFF
                    == ord("q")
                ):
                    break

            # =====================================================
            # FINAL SESSION DATA
            # =====================================================

            left_rom_result = (
                get_rom(
                    left_pipeline
                )
            )

            right_rom_result = (
                get_rom(
                    right_pipeline
                )
            )

            left_history = (
                left_pipeline.angle_history
            )

            right_history = (
                right_pipeline.angle_history
            )

            left_rom_average = (
                sum(left_history)
                / len(left_history)
                if left_history
                else None
            )

            right_rom_average = (
                sum(right_history)
                / len(right_history)
                if right_history
                else None
            )

            # -----------------------------------------------------
            # Digital Thread final result
            #
            # Repetition data is no longer displayed by the live
            # interface. The existing Digital Thread schema still
            # contains the field, so we leave the backend untouched
            # for this UI cleanup stage.
            # -----------------------------------------------------

            thread.record_result(
                repetitions=0,

                rom_min=(
                    left_rom_result[
                        "min_angle"
                    ]
                    if left_rom_result[
                        "min_angle"
                    ] is not None
                    else right_rom_result[
                        "min_angle"
                    ]
                ),

                rom_max=(
                    left_rom_result[
                        "max_angle"
                    ]
                    if left_rom_result[
                        "max_angle"
                    ] is not None
                    else right_rom_result[
                        "max_angle"
                    ]
                ),

                rom_average=(
                    left_rom_average
                    if left_rom_average
                    is not None
                    else right_rom_average
                ),

                performance_score=None,

                feedback=(
                    "ROM tracking session completed."
                )
            )

            thread.end_session()

            # -----------------------------------------------------
            # Export
            # -----------------------------------------------------

            os.makedirs(
                args.export_dir,
                exist_ok=True
            )

            export_path = os.path.join(
                args.export_dir,
                f"{session_id}.json"
            )

            thread_export = DigitalThread(
                args.database_url
            )

            thread_export.export_session(
                session_id,
                export_path
            )

        except Exception:

            raise

        finally:

            cap.release()

            pose.close()

            cv2.destroyAllWindows()

    # -----------------------------------------------------------------
    # Final console output
    # -----------------------------------------------------------------

    print()

    print(
        "=============================================="
    )

    print(
        "             ROM SESSION SUMMARY"
    )

    print(
        "=============================================="
    )

    print(
        f"Accepted frames: {frame_id}"
    )

    print(
        f"Valid frames: "
        f"{pose_validator.total_valid_frames}"
    )

    print(
        f"Invalid frames: "
        f"{pose_validator.total_invalid_frames}"
    )

    print(
        f"Final tracking state: "
        f"{pose_validator.state}"
    )

    print(
        f"Left ROM: "
        f"{format_value(left_rom_result.get('rom'), ' deg')}"
    )

    print(
        f"Right ROM: "
        f"{format_value(right_rom_result.get('rom'), ' deg')}"
    )

    print(
        f"CSV: {OUTPUT_FILE}"
    )

    if export_path is not None:

        print(
            f"Digital Thread: {export_path}"
        )

    print(
        "=============================================="
    )


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    main()