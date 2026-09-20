EXERCISES = {
    "elbow_flexion": {
        "name": "Elbow Flexion",
        "joint_angle": "left_elbow",
        "movement_type": "flexion_extension",
        "description": "Bend and straighten the elbow."
    },

    "shoulder_flexion": {
        "name": "Shoulder Flexion",
        "joint_angle": "left_shoulder",
        "movement_type": "flexion_extension",
        "description": "Raise and lower the arm in front of the body."
    }
}


def get_exercise(exercise_id):
    """Return the definition of an exercise."""

    if exercise_id not in EXERCISES:
        raise ValueError(f"Unknown exercise: {exercise_id}")

    return EXERCISES[exercise_id]