import numpy as np

def calculate_angle(a, b, c):
    """
    Calculates the angle at point b, given three points a-b-c.
    Each point is a dict with 'x' and 'y' keys.
    """
    a = np.array([a["x"], a["y"]])
    b = np.array([b["x"], b["y"]])
    c = np.array([c["x"], c["y"]])

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    angle = np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))
    return angle