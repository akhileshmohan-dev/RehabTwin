EXERCISE_CONFIG = {
    "elbow_flexion": {
        "flexed_threshold": 100,
        "extended_threshold": 160,

        "left": {
            "angle_name": "left_elbow",
            "landmarks": [
                "LEFT_SHOULDER",
                "LEFT_ELBOW",
                "LEFT_WRIST",
            ],
        },

        "right": {
            "angle_name": "right_elbow",
            "landmarks": [
                "RIGHT_SHOULDER",
                "RIGHT_ELBOW",
                "RIGHT_WRIST",
            ],
        },
    },

    "shoulder_flexion": {
        "flexed_threshold": 60,
        "extended_threshold": 160,

        "left": {
            "angle_name": "left_shoulder",
            "landmarks": [
                "LEFT_HIP",
                "LEFT_SHOULDER",
                "LEFT_ELBOW",
            ],
        },

        "right": {
            "angle_name": "right_shoulder",
            "landmarks": [
                "RIGHT_HIP",
                "RIGHT_SHOULDER",
                "RIGHT_ELBOW",
            ],
        },
    },

    "shoulder_abduction": {
        "flexed_threshold": 60,
        "extended_threshold": 160,

        "left": {
            "angle_name": "left_shoulder",
            "landmarks": [
                "LEFT_HIP",
                "LEFT_SHOULDER",
                "LEFT_ELBOW",
            ],
        },

        "right": {
            "angle_name": "right_shoulder",
            "landmarks": [
                "RIGHT_HIP",
                "RIGHT_SHOULDER",
                "RIGHT_ELBOW",
            ],
        },
    },

    "knee_flexion": {
        "flexed_threshold": 100,
        "extended_threshold": 160,

        "left": {
            "angle_name": "left_knee",
            "landmarks": [
                "LEFT_HIP",
                "LEFT_KNEE",
                "LEFT_ANKLE",
            ],
        },

        "right": {
            "angle_name": "right_knee",
            "landmarks": [
                "RIGHT_HIP",
                "RIGHT_KNEE",
                "RIGHT_ANKLE",
            ],
        },
    },
}