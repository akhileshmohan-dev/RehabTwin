import csv
import os
import sys

import cv2
import mediapipe as mp

from rehabilitation.session_assessment import SessionAssessment

from mediapipe.python.solutions import pose as mp_pose
from mediapipe.python.solutions import drawing_utils as mp_drawing


# ---------------------------------------------------------
# Repository root
# ---------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------
# Allow imports from pose_estimation/
# ---------------------------------------------------------

POSE_DIR = os.path.join(
    PROJECT_ROOT,
    "pose_estimation"
)

if POSE_DIR not in sys.path:
    sys.path.insert(0, POSE_DIR)


from landmark_extractor import extract_landmarks
from angle_utils import calculate_angle
from pose_output import create_pose_frame

from rehabilitation.analysis_pipeline import (
    RehabilitationAnalysisPipeline
)
from rehabilitation.exercise_config import EXERCISE_CONFIG
from digital_thread.thread import DigitalThread


# ---------------------------------------------------------
# Exercise selection
# ---------------------------------------------------------

EXERCISE = "shoulder_abduction"
# ---------------------------------------------------------
# Exercise configuration
# ---------------------------------------------------------

exercise_config = EXERCISE_CONFIG[EXERCISE]

left_config = exercise_config["left"]
right_config = exercise_config["right"]

LEFT_ANGLE_NAME = left_config["angle_name"]
RIGHT_ANGLE_NAME = right_config["angle_name"]


# ---------------------------------------------------------
# Output file
# ---------------------------------------------------------

OUTPUT_FILE = os.path.join(
    os.path.dirname(__file__),
    f"{EXERCISE}_motion.csv"
)


# ---------------------------------------------------------
# MediaPipe Pose
# ---------------------------------------------------------

pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


# ---------------------------------------------------------
# Camera
# ---------------------------------------------------------

cap = cv2.VideoCapture(0)


# ---------------------------------------------------------
# Separate rehabilitation pipelines
# ---------------------------------------------------------

left_pipeline = RehabilitationAnalysisPipeline(
    exercise=EXERCISE,
    side="left",
    smoothing_window=5
)

right_pipeline = RehabilitationAnalysisPipeline(
    exercise=EXERCISE,
    side="right",
    smoothing_window=5
)


# ---------------------------------------------------------
# Separate movement-quality assessments
# ---------------------------------------------------------

left_assessment = SessionAssessment()
right_assessment = SessionAssessment()


# ---------------------------------------------------------
# Digital Thread
# ---------------------------------------------------------

digital_thread = DigitalThread()

patient_id = "TEST-001"

session_id = digital_thread.start_session(
    patient_id=patient_id,
    exercise=EXERCISE
)

print(
    f"Digital Thread session started: {session_id}"
)

print(
    f"Starting bilateral {EXERCISE} data collection."
)

print(
    f"Perform {EXERCISE.replace('_', ' ')} movements."
)

print("Press 'q' to stop.")


# ---------------------------------------------------------
# CSV
# ---------------------------------------------------------

frame_id = 0

with open(
    OUTPUT_FILE,
    "w",
    newline=""
) as csv_file:

    writer = csv.writer(csv_file)

    writer.writerow([
        "timestamp",

        # Left side
        f"left_raw_{LEFT_ANGLE_NAME}",
        f"left_smoothed_{LEFT_ANGLE_NAME}",
        "left_state",
        "left_repetitions",
        "left_rom_min",
        "left_rom_max",
        "left_rom",

        # Right side
        f"right_raw_{RIGHT_ANGLE_NAME}",
        f"right_smoothed_{RIGHT_ANGLE_NAME}",
        "right_state",
        "right_repetitions",
        "right_rom_min",
        "right_rom_max",
        "right_rom",
    ])


    # -----------------------------------------------------
    # Main camera loop
    # -----------------------------------------------------

    while cap.isOpened():

        ret, frame = cap.read()

        if not ret:
            break


        # -------------------------------------------------
        # Convert BGR → RGB
        # -------------------------------------------------

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )


        # -------------------------------------------------
        # MediaPipe pose detection
        # -------------------------------------------------

        results = pose.process(rgb_frame)

        pose_frame = None


        if results.pose_landmarks:

            # Draw skeleton
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS
            )


            h, w, _ = frame.shape


            # -------------------------------------------------
            # Extract landmarks
            # -------------------------------------------------

            landmarks = extract_landmarks(
                results,
                w,
                h
            )


            angles = {}


            if landmarks:

                # =============================================
                # LEFT SIDE ANGLE
                # =============================================

                left_landmarks = left_config["landmarks"]

                if all(
                    landmark in landmarks
                    for landmark in left_landmarks
                ):

                    point_a = landmarks[
                        left_landmarks[0]
                    ]

                    point_b = landmarks[
                        left_landmarks[1]
                    ]

                    point_c = landmarks[
                        left_landmarks[2]
                    ]

                    angles[LEFT_ANGLE_NAME] = calculate_angle(
                        point_a,
                        point_b,
                        point_c
                    )


                # =============================================
                # RIGHT SIDE ANGLE
                # =============================================

                right_landmarks = right_config["landmarks"]

                if all(
                    landmark in landmarks
                    for landmark in right_landmarks
                ):

                    point_a = landmarks[
                        right_landmarks[0]
                    ]

                    point_b = landmarks[
                        right_landmarks[1]
                    ]

                    point_c = landmarks[
                        right_landmarks[2]
                    ]

                    angles[RIGHT_ANGLE_NAME] = calculate_angle(
                        point_a,
                        point_b,
                        point_c
                    )


                # -------------------------------------------------
                # Create pose frame if at least one angle exists
                # -------------------------------------------------

                if angles:

                    pose_frame = create_pose_frame(
                        landmarks,
                        angles
                    )


        # -----------------------------------------------------
        # Rehabilitation analysis
        # -----------------------------------------------------

        if pose_frame is not None:

            frame_id += 1


            # Process both sides
            left_result = left_pipeline.process(
                pose_frame
            )

            right_result = right_pipeline.process(
                pose_frame
            )


            # -------------------------------------------------
            # Digital Thread
            # -------------------------------------------------

            digital_thread.record_frame(
                frame_id=frame_id,
                landmarks=pose_frame["landmarks"],
                joint_angles=pose_frame["angles"],

                phase=(
                    f"L:{left_result['state']} "
                    f"R:{right_result['state']}"
                )
            )


            # -------------------------------------------------
            # Extract results
            # -------------------------------------------------

            left_raw_angle = left_result["raw_angle"]
            left_smoothed_angle = left_result[
                "smoothed_angle"
            ]
            left_rom = left_result["rom"]

            right_raw_angle = right_result["raw_angle"]
            right_smoothed_angle = right_result[
                "smoothed_angle"
            ]
            right_rom = right_result["rom"]


            timestamp = pose_frame["timestamp"]


            # -------------------------------------------------
            # Save CSV row
            # -------------------------------------------------

            writer.writerow([
                timestamp,

                # Left
                left_raw_angle,
                left_smoothed_angle,
                left_result["state"],
                left_result["repetitions"],
                left_rom["min_angle"],
                left_rom["max_angle"],
                left_rom["rom"],

                # Right
                right_raw_angle,
                right_smoothed_angle,
                right_result["state"],
                right_result["repetitions"],
                right_rom["min_angle"],
                right_rom["max_angle"],
                right_rom["rom"],
            ])


            # -------------------------------------------------
            # Display LEFT side
            # -------------------------------------------------

            left_angle_text = (
                f"Left {LEFT_ANGLE_NAME}: "
                f"{left_smoothed_angle:.1f}"
                if left_smoothed_angle is not None
                else
                f"Left {LEFT_ANGLE_NAME}: --"
            )

            left_rom_text = (
                f"Left ROM: {left_rom['rom']:.1f}"
                if left_rom["rom"] is not None
                else
                "Left ROM: --"
            )


            cv2.putText(
                frame,
                left_angle_text,
                (10, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Left Reps: "
                f"{left_result['repetitions']}",
                (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                left_rom_text,
                (10, 95),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )


            # -------------------------------------------------
            # Display RIGHT side
            # -------------------------------------------------

            right_angle_text = (
                f"Right {RIGHT_ANGLE_NAME}: "
                f"{right_smoothed_angle:.1f}"
                if right_smoothed_angle is not None
                else
                f"Right {RIGHT_ANGLE_NAME}: --"
            )

            right_rom_text = (
                f"Right ROM: {right_rom['rom']:.1f}"
                if right_rom["rom"] is not None
                else
                "Right ROM: --"
            )


            cv2.putText(
                frame,
                right_angle_text,
                (10, 135),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Right Reps: "
                f"{right_result['repetitions']}",
                (10, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                right_rom_text,
                (10, 195),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )


        # -----------------------------------------------------
        # Show camera
        # -----------------------------------------------------

        cv2.imshow(
            f"RehabTwin - "
            f"{EXERCISE.replace('_', ' ').title()}",
            frame
        )


        # -----------------------------------------------------
        # Quit
        # -----------------------------------------------------

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


# ---------------------------------------------------------
# Cleanup
# ---------------------------------------------------------

cap.release()
pose.close()
cv2.destroyAllWindows()


# ---------------------------------------------------------
# Final results
# ---------------------------------------------------------

left_final = left_pipeline.process(None)
right_final = right_pipeline.process(None)


# ---------------------------------------------------------
# Left movement-quality assessment
# ---------------------------------------------------------

left_assessment_result = left_assessment.assess(
    exercise=EXERCISE,
    angle_history=left_pipeline.angle_history,
    repetitions=left_final["repetitions"],
)

left_quality = left_assessment_result[
    "movement_quality"
]


# ---------------------------------------------------------
# Right movement-quality assessment
# ---------------------------------------------------------

right_assessment_result = right_assessment.assess(
    exercise=EXERCISE,
    angle_history=right_pipeline.angle_history,
    repetitions=right_final["repetitions"],
)

right_quality = right_assessment_result[
    "movement_quality"
]


# ---------------------------------------------------------
# Final ROM
# ---------------------------------------------------------

left_rom_result = left_final["rom"]
right_rom_result = right_final["rom"]


# ---------------------------------------------------------
# Record LEFT result in Digital Thread
# ---------------------------------------------------------

digital_thread.record_result(
    repetitions=left_final["repetitions"],
    rom_min=left_rom_result["min_angle"],
    rom_max=left_rom_result["max_angle"],
    rom_average=None,
    performance_score=None,
    feedback=(
        f"Left movement quality: "
        f"{left_quality or 'N/A'}"
    )
)


# ---------------------------------------------------------
# Record RIGHT result in Digital Thread
# ---------------------------------------------------------

digital_thread.record_result(
    repetitions=right_final["repetitions"],
    rom_min=right_rom_result["min_angle"],
    rom_max=right_rom_result["max_angle"],
    rom_average=None,
    performance_score=None,
    feedback=(
        f"Right movement quality: "
        f"{right_quality or 'N/A'}"
    )
)


# ---------------------------------------------------------
# End Digital Thread session
# ---------------------------------------------------------

digital_thread.end_session()


# ---------------------------------------------------------
# Final console output
# ---------------------------------------------------------

print(
    f"\nDigital Thread session completed: "
    f"{session_id}"
)

print(
    f"Left movement quality: "
    f"{left_quality or 'N/A'}"
)

print(
    f"Right movement quality: "
    f"{right_quality or 'N/A'}"
)

print(
    f"Left repetitions: "
    f"{left_final['repetitions']}"
)

print(
    f"Right repetitions: "
    f"{right_final['repetitions']}"
)

print(
    f"Left ROM: "
    f"{left_rom_result['rom']}"
)

print(
    f"Right ROM: "
    f"{right_rom_result['rom']}"
)

print(
    f"Data saved to: {OUTPUT_FILE}"
)