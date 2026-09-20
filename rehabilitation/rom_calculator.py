def calculate_rom(angle_series):
    """
    Calculate the basic range of motion from a sequence of joint angles.

    ROM = maximum angle - minimum angle

    Parameters
    ----------
    angle_series : list[float]
        Sequence of valid joint-angle measurements in degrees.

    Returns
    -------
    dict
        Minimum angle, maximum angle, and ROM.
    """

    if not angle_series:
        return {
            "min_angle": None,
            "max_angle": None,
            "rom": None
        }

    min_angle = min(angle_series)
    max_angle = max(angle_series)

    return {
        "min_angle": min_angle,
        "max_angle": max_angle,
        "rom": max_angle - min_angle
    }