import mediapipe as mp

mp_pose = mp.solutions.pose

def extract_landmarks(results, frame_width, frame_height):
    """
    Returns structured landmark data with pixel coordinates and visibility.
    Returns None if no pose detected.
    """
    if not results.pose_landmarks:
        return None

    landmarks = {}
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        name = mp_pose.PoseLandmark(idx).name
        landmarks[name] = {
            "x": lm.x * frame_width,
            "y": lm.y * frame_height,
            "z": lm.z,
            "visibility": lm.visibility
        }
    return landmarks
