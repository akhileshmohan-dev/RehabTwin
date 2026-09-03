import csv
import os
import sys
import time

import cv2
import mediapipe as mp


from rehabilitation.session_assessment import SessionAssessment

from mediapipe.python.solutions import pose as mp_pose
from mediapipe.python.solutions import drawing_utils as mp_drawing

# Repository root
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Allow imports from pose_estimation/
POSE_DIR = os.path.join(
    PROJECT_ROOT,
    "pose_estimation"
)

if POSE_DIR not in sys.path:
    sys.path.insert(0, POSE_DIR)

from landmark_extractor import extract_landmarks
from angle_utils import calculate_angle
from pose_output import create_pose_frame

from rehabilitation.analysis_pipeline import RehabilitationAnalysisPipeline
from rehabilitation.exercise_config import EXERCISE_CONFIG
from digital_thread.thread import DigitalThread


EXERCISE = "shoulder_flexion"


OUTPUT_FILE = os.path.join(
    os.path.dirname(__file__),
    f"{EXERCISE}_motion.csv"
)

exercise_config = EXERCISE_CONFIG[EXERCISE]
ANGLE_NAME = exercise_config["angle_name"]


pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0)

pipeline = RehabilitationAnalysisPipeline(
    exercise=EXERCISE,
    smoothing_window=5
)
session_assessment = SessionAssessment()
digital_thread = DigitalThread()

patient_id = "TEST-001"

session_id = digital_thread.start_session(
    patient_id=patient_id,
    exercise=EXERCISE
)

print(f"Digital Thread session started: {session_id}")

print(f"Starting {EXERCISE} data collection.")
print(f"Perform {EXERCISE.replace('_', ' ')} movements.")
print("Press 'q' to stop.")


frame_id = 0
with open(OUTPUT_FILE, "w", newline="") as csv_file:

    writer = csv.writer(csv_file)

    writer.writerow([
        "timestamp",
        f"raw_{ANGLE_NAME}",
        f"smoothed_{ANGLE_NAME}",
        "state",
        "repetitions",
        "rom_min",
        "rom_max",
        "rom",
    ])

    while cap.isOpened():

        ret, frame = cap.read()

        if not ret:
            break

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        results = pose.process(rgb_frame)

        pose_frame = None

        if results.pose_landmarks:

            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS
            )

            h, w, _ = frame.shape

            landmarks = extract_landmarks(
                results,
                w,
                h
            )

            angles = None

            if landmarks:

                required_landmarks = exercise_config["landmarks"]

                if all(
                    landmark in landmarks
                    for landmark in required_landmarks
                ):

                    point_a = landmarks[required_landmarks[0]]
                    point_b = landmarks[required_landmarks[1]]
                    point_c = landmarks[required_landmarks[2]]

                    angle = calculate_angle(
                        point_a,
                        point_b,
                        point_c
                    )

                    angles = {
                        ANGLE_NAME: angle
                    }
                    pose_frame = create_pose_frame(
                        landmarks,
                        angles
                    )
                    print(
                    "Shoulder visibility:",
                    pose_frame["visibility"].get("LEFT_HIP"),
                    pose_frame["visibility"].get("LEFT_SHOULDER"),
                    pose_frame["visibility"].get("LEFT_ELBOW")
                    )

        if pose_frame is not None:

            frame_id += 1

            analysis_result = pipeline.process(
                pose_frame
            )


            digital_thread.record_frame(
                frame_id=frame_id,
                landmarks=pose_frame["landmarks"],
                joint_angles=pose_frame["angles"],
                phase=analysis_result["state"],
            )

            raw_angle = analysis_result["raw_angle"]
            smoothed_angle = analysis_result["smoothed_angle"]
            rom_result = analysis_result["rom"]

            timestamp = pose_frame["timestamp"]

            writer.writerow([
                timestamp,
                raw_angle,
                smoothed_angle,
                analysis_result["state"],
                analysis_result["repetitions"],
                rom_result["min_angle"],
                rom_result["max_angle"],
                rom_result["rom"],
            ])

            if smoothed_angle is not None:

                cv2.putText(
                    frame,
                    f"{ANGLE_NAME}: {smoothed_angle:.1f}",
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
                cv2.putText(
                frame,
                f"Reps: {analysis_result['repetitions']}",
                (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
                )
                cv2.putText(
                    frame,
                    f"ROM: {rom_result['rom']:.1f}" if rom_result["rom"] is not None else "ROM: --",
                    (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
                

        cv2.imshow(
            f"RehabTwin - {EXERCISE.replace('_', ' ').title()}",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cap.release()
pose.close()
cv2.destroyAllWindows()

final_result = pipeline.process(None)

rom_result = final_result["rom"]

session_assessment_result = session_assessment.assess(
    exercise=EXERCISE,
    angle_history=pipeline.angle_history,
    repetitions=final_result["repetitions"],
)

movement_quality = session_assessment_result["movement_quality"]

digital_thread.record_result(
    repetitions=final_result["repetitions"],
    rom_min=rom_result["min_angle"],
    rom_max=rom_result["max_angle"],
    rom_average=None,
    performance_score=None,
    feedback=movement_quality or ""
)

digital_thread.end_session()

print(f"\nDigital Thread session completed: {session_id}")
print(f"Movement quality: {movement_quality or 'N/A'}")
print(f"Data saved to: {OUTPUT_FILE}")