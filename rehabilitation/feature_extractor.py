import statistics


def extract_features(
    exercise,
    angle_history,
    repetitions,
):
    """
    Extract ML features from rehabilitation analysis data.

    Parameters
    ----------
    exercise : str
        Name of the exercise.
    angle_history : list[float]
        Smoothed joint-angle measurements.
    repetitions : int
        Number of completed repetitions.

    Returns
    -------
    dict
        Feature values for ML prediction.
    """

    if not angle_history:
        return {
            "exercise": exercise,
            "min_angle": None,
            "max_angle": None,
            "rom": None,
            "average_angle": None,
            "angle_variability": None,
            "repetitions": repetitions,
        }

    min_angle = min(angle_history)
    max_angle = max(angle_history)
    rom = max_angle - min_angle
    average_angle = statistics.mean(angle_history)

    if len(angle_history) > 1:
        angle_variability = statistics.stdev(angle_history)
    else:
        angle_variability = 0.0

    return {
        "exercise": exercise,
        "min_angle": min_angle,
        "max_angle": max_angle,
        "rom": rom,
        "average_angle": average_angle,
        "angle_variability": angle_variability,
        "repetitions": repetitions,
    }