import socket
import json


UNITY_IP = "127.0.0.1"
UNITY_PORT = 5005


_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send_pose(landmarks):
    """
    Send MediaPipe pose landmarks to Unity.

    Each landmark contains:
        - Image-space x, y, z
        - Visibility
        - World-space x, y, z
    """

    if not landmarks:
        return

    landmark_list = []

    for name, lm in landmarks.items():

        landmark_list.append({
            "name": name,

            # Image-space coordinates
            "x": lm["x"],
            "y": lm["y"],
            "z": lm["z"],

            # Visibility
            "visibility": lm["visibility"],

            # MediaPipe world coordinates
            "world_x": lm.get("world_x", 0.0),
            "world_y": lm.get("world_y", 0.0),
            "world_z": lm.get("world_z", 0.0)
        })

    data = {
        "landmarks": landmark_list
    }

    message = json.dumps(data)

    _socket.sendto(
        message.encode("utf-8"),
        (UNITY_IP, UNITY_PORT)
    )