import os
import sys

# =========================================================
# PROJECT PATHS
# =========================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

POSE_DIR = os.path.join(
    PROJECT_ROOT,
    "pose_estimation"
)

if POSE_DIR not in sys.path:
    sys.path.insert(0, POSE_DIR)


# =========================================================
# IMPORTS
# =========================================================

import cv2
import mediapipe as mp

from landmark_extractor import extract_landmarks

from rehabilitation.posture_detector import (
    PostureDetector,
    validate_setup
)

from mediapipe.python.solutions import pose as mp_pose
from mediapipe.python.solutions import drawing_utils as mp_drawing


# =========================================================
# MEDIAPIPE
# =========================================================

pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


# =========================================================
# CAMERA
# =========================================================

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open camera.")
    sys.exit(1)


# =========================================================
# POSTURE DETECTOR
# =========================================================

detector = PostureDetector()


print("Starting RehabTwin posture test.")
print("Keep your full body visible.")
print("You can face the camera or stand sideways.")
print("Press 'q' to quit.")


# =========================================================
# MAIN LOOP
# =========================================================

while cap.isOpened():

    ret, frame = cap.read()

    if not ret:
        print("Error: Could not read frame.")
        break

    # -----------------------------------------------------
    # Convert BGR → RGB
    # -----------------------------------------------------

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    # -----------------------------------------------------
    # MediaPipe Pose
    # -----------------------------------------------------

    results = pose.process(
        rgb_frame
    )

    # Default values
    posture = "UNKNOWN"
    setup_ready = False
    setup_message = "No person detected"

    smoothed_ratio = None
    smoothed_angle = None

    # =====================================================
    # POSE DETECTED
    # =====================================================

    if results.pose_landmarks:

        # -------------------------------------------------
        # Draw landmarks
        # -------------------------------------------------

        mp_drawing.draw_landmarks(
            frame,
            results.pose_landmarks,
            mp_pose.POSE_CONNECTIONS
        )

        # -------------------------------------------------
        # Frame dimensions
        # -------------------------------------------------

        h, w, _ = frame.shape

        # -------------------------------------------------
        # Extract landmarks
        # -------------------------------------------------

        landmarks = extract_landmarks(
            results,
            w,
            h
        )

        # =================================================
        # SETUP VALIDATION
        # =================================================

        setup = validate_setup(
            landmarks
        )

        setup_ready = setup["ready"]
        setup_message = setup["message"]

        # =================================================
        # POSTURE DETECTION
        # =================================================

        result = detector.update(
            landmarks
        )

        posture = result["posture"]

        smoothed_ratio = result[
            "smoothed_hip_knee_ratio"
        ]

        smoothed_angle = result[
            "smoothed_knee_angle"
        ]

        # =================================================
        # DISPLAY SETUP STATUS
        # =================================================

        if setup_ready:

            cv2.putText(
                frame,
                "SETUP: READY",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

        else:

            cv2.putText(
                frame,
                "SETUP: NOT READY",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

            cv2.putText(
                frame,
                setup_message,
                (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 255),
                2
            )

        # =================================================
        # DISPLAY POSTURE
        # =================================================

        cv2.putText(
            frame,
            f"Posture: {posture}",
            (10, 95),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2
        )

        # =================================================
        # DISPLAY RATIO
        # =================================================

        if smoothed_ratio is not None:

            cv2.putText(
                frame,
                f"Hip-Knee Ratio: "
                f"{smoothed_ratio:.2f}",
                (10, 130),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

        else:

            cv2.putText(
                frame,
                "Hip-Knee Ratio: --",
                (10, 130),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

        # =================================================
        # DISPLAY KNEE ANGLE
        # =================================================

        if smoothed_angle is not None:

            cv2.putText(
                frame,
                f"Knee Angle: "
                f"{smoothed_angle:.1f}",
                (10, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

        else:

            cv2.putText(
                frame,
                "Knee Angle: --",
                (10, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2
            )

        # =================================================
        # DISPLAY VISIBILITY
        # =================================================

        cv2.putText(
            frame,
            f"Visible: "
            f"{setup['visible_count']}/8",
            (10, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"Visibility: "
            f"{setup['visibility_score']:.2f}",
            (10, 235),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2
        )

    # =====================================================
    # NO POSE DETECTED
    # =====================================================

    else:

        cv2.putText(
            frame,
            "SETUP: NOT READY",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

        cv2.putText(
            frame,
            "No person detected",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )

        cv2.putText(
            frame,
            "Posture: UNKNOWN",
            (10, 95),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2
        )

    # =====================================================
    # SHOW FRAME
    # =====================================================

    cv2.imshow(
        "RehabTwin - Posture Test",
        frame
    )

    # =====================================================
    # QUIT
    # =====================================================

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


# =========================================================
# CLEANUP
# =========================================================

cap.release()
pose.close()
cv2.destroyAllWindows()

print("\nPosture test completed.")