import mediapipe as mp

mp_pose = mp.solutions.pose


def extract_landmarks(results, frame_width, frame_height):
    """
    Extract MediaPipe pose landmarks.

    Returns:
        dict:
        {
            "LEFT_SHOULDER": {
                "x": ...,
                "y": ...,
                "z": ...,
                "visibility": ...,
                "world_x": ...,
                "world_y": ...,
                "world_z": ...
            },
            ...
        }

    x/y:
        Pixel coordinates from the camera image.

    z:
        MediaPipe image-space relative depth.

    world_x/world_y/world_z:
        MediaPipe pose world coordinates.
    """

    if not results.pose_landmarks:
        return None

    landmarks = {}

    # ---------------------------------------------------------
    # World landmarks
    # ---------------------------------------------------------
    #
    # MediaPipe provides these separately from the normal
    # image landmarks.
    #
    # They are expressed in a body/world coordinate system
    # and are more useful for 3D pose reconstruction.
    #
    world_landmarks = None

    if results.pose_world_landmarks:
        world_landmarks = results.pose_world_landmarks.landmark

    # ---------------------------------------------------------
    # Extract landmarks
    # ---------------------------------------------------------

    for idx, lm in enumerate(results.pose_landmarks.landmark):

        name = mp_pose.PoseLandmark(idx).name

        landmark_data = {
            # Existing image-space coordinates
            "x": lm.x * frame_width,
            "y": lm.y * frame_height,
            "z": lm.z,

            # Visibility
            "visibility": lm.visibility,

            # World coordinates
            "world_x": 0.0,
            "world_y": 0.0,
            "world_z": 0.0,
        }

        # -----------------------------------------------------
        # Add world coordinates if available
        # -----------------------------------------------------

        if world_landmarks is not None and idx < len(world_landmarks):

            world_lm = world_landmarks[idx]

            landmark_data["world_x"] = world_lm.x
            landmark_data["world_y"] = world_lm.y
            landmark_data["world_z"] = world_lm.z

        landmarks[name] = landmark_data

    return landmarks