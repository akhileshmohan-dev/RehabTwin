import cv2
import mediapipe as mp
from landmark_extractor import extract_landmarks
from angle_utils import calculate_angle

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

cap = cv2.VideoCapture(0)
cv2.namedWindow("Pose Estimation", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Pose Estimation", 1280, 720)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = pose.process(rgb_frame)

    if results.pose_landmarks:
        mp_drawing.draw_landmarks(
            frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS
        )

        h, w, _ = frame.shape
        landmarks = extract_landmarks(results, w, h)

        if landmarks:
            # Left elbow angle
            l_shoulder = landmarks["LEFT_SHOULDER"]
            l_elbow = landmarks["LEFT_ELBOW"]
            l_wrist = landmarks["LEFT_WRIST"]
            left_elbow_angle = calculate_angle(l_shoulder, l_elbow, l_wrist)

            # Right elbow angle
            r_shoulder = landmarks["RIGHT_SHOULDER"]
            r_elbow = landmarks["RIGHT_ELBOW"]
            r_wrist = landmarks["RIGHT_WRIST"]
            right_elbow_angle = calculate_angle(r_shoulder, r_elbow, r_wrist)

            # Left shoulder angle
            l_hip = landmarks["LEFT_HIP"]
            left_shoulder_angle = calculate_angle(l_hip, l_shoulder, l_elbow)

            # Right shoulder angle
            r_hip = landmarks["RIGHT_HIP"]
            right_shoulder_angle = calculate_angle(r_hip, r_shoulder, r_elbow)

            cv2.putText(frame, f"L Elbow: {int(left_elbow_angle)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, f"R Elbow: {int(right_elbow_angle)}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, f"L Shoulder: {int(left_shoulder_angle)}", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.putText(frame, f"R Shoulder: {int(right_shoulder_angle)}", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow("Pose Estimation", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    

cap.release()
cv2.destroyAllWindows()