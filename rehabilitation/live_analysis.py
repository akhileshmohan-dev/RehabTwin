import csv
import os
import sys
import time

import cv2
import mediapipe as mp

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

from rehabilitation.analysis_pipeline import ElbowAnalysisPipeline


OUTPUT_FILE = os.path.join(
    os.path.dirname(__file__),
    "elbow_motion.csv"
)


pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0)

pipeline = ElbowAnalysisPipeline(
    smoothing_window=5,
    flexed_threshold=100,
    extended_threshold=160
)

print("Starting elbow-motion data collection.")
print("Perform elbow flexion movements.")
print("Press 'q' to stop.")

with open(OUTPUT_FILE, "w", newline="") as csv_file:

    writer = csv.writer(csv_file)

    writer.writerow([
        "timestamp",
        "raw_left_elbow",
        "smoothed_left_elbow",
        "state",
        "repetitions",
        "rom_min",
        "rom_max",
        "rom"
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

                left_shoulder = landmarks["LEFT_SHOULDER"]
                left_elbow = landmarks["LEFT_ELBOW"]
                left_wrist = landmarks["LEFT_WRIST"]

                left_elbow_angle = calculate_angle(
                    left_shoulder,
                    left_elbow,
                    left_wrist
                )

                angles = {
                    "left_elbow": left_elbow_angle
                }

                pose_frame = create_pose_frame(
                    landmarks,
                    angles
                )

        if pose_frame is not None:

            raw_angle = pose_frame["angles"].get(
                "left_elbow"
            )

            analysis_result = pipeline.process(
                pose_frame
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
                rom_result["rom"]
            ])

            if smoothed_angle is not None:

                cv2.putText(
                    frame,
                    f"Elbow: {smoothed_angle:.1f}",
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
            "RehabTwin - Elbow Analysis",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

cap.release()
pose.close()
cv2.destroyAllWindows()

print(f"\nData saved to: {OUTPUT_FILE}")