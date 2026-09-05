import math
from collections import deque


# =========================================================
# SETTINGS
# =========================================================

MIN_VISIBILITY = 0.20

SMOOTHING_WINDOW = 10
REQUIRED_FRAMES = 6

# Posture thresholds based on the observed
# front-facing camera measurements.
#
# Standing: approximately 0.64 - 0.65
# Sitting:  approximately 0.26 - 0.29
#
# The gap between 0.40 and 0.50 is treated as
# an uncertain transition region.

STANDING_RATIO_THRESHOLD = 0.50
SITTING_RATIO_THRESHOLD = 0.40


# =========================================================
# GEOMETRY
# =========================================================

def distance_3d(a, b):
    return math.sqrt(
        (a["x"] - b["x"]) ** 2 +
        (a["y"] - b["y"]) ** 2 +
        (a["z"] - b["z"]) ** 2
    )


def calculate_knee_angle_3d(hip, knee, ankle):

    a = (
        hip["x"] - knee["x"],
        hip["y"] - knee["y"],
        hip["z"] - knee["z"]
    )

    b = (
        ankle["x"] - knee["x"],
        ankle["y"] - knee["y"],
        ankle["z"] - knee["z"]
    )

    magnitude_a = math.sqrt(
        a[0] ** 2 +
        a[1] ** 2 +
        a[2] ** 2
    )

    magnitude_b = math.sqrt(
        b[0] ** 2 +
        b[1] ** 2 +
        b[2] ** 2
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return None

    dot = (
        a[0] * b[0] +
        a[1] * b[1] +
        a[2] * b[2]
    )

    cosine = dot / (
        magnitude_a * magnitude_b
    )

    cosine = max(
        -1.0,
        min(1.0, cosine)
    )

    return math.degrees(
        math.acos(cosine)
    )


# =========================================================
# VISIBILITY
# =========================================================

def is_visible(point):

    if point is None:
        return False

    return point.get(
        "visibility",
        1.0
    ) >= MIN_VISIBILITY


# =========================================================
# SIDE FEATURES
# =========================================================

def analyse_side(landmarks, side):

    prefix = side.upper()

    shoulder_name = f"{prefix}_SHOULDER"
    hip_name = f"{prefix}_HIP"
    knee_name = f"{prefix}_KNEE"
    ankle_name = f"{prefix}_ANKLE"

    required = [
        shoulder_name,
        hip_name,
        knee_name,
        ankle_name
    ]

    if not all(
        name in landmarks
        for name in required
    ):
        return None

    shoulder = landmarks[shoulder_name]
    hip = landmarks[hip_name]
    knee = landmarks[knee_name]
    ankle = landmarks[ankle_name]

    if not all(
        is_visible(point)
        for point in (
            shoulder,
            hip,
            knee,
            ankle
        )
    ):
        return None

    # -----------------------------------------------------
    # Body scale
    # -----------------------------------------------------

    torso_length = distance_3d(
        shoulder,
        hip
    )

    if torso_length < 0.01:
        return None

    # -----------------------------------------------------
    # Vertical body relationships
    # -----------------------------------------------------

    hip_knee_vertical = abs(
        hip["y"] - knee["y"]
    )

    knee_ankle_vertical = abs(
        knee["y"] - ankle["y"]
    )

    shoulder_hip_vertical = abs(
        shoulder["y"] - hip["y"]
    )

    # -----------------------------------------------------
    # Normalize by torso length
    # -----------------------------------------------------

    hip_knee_ratio = (
        hip_knee_vertical /
        torso_length
    )

    knee_ankle_ratio = (
        knee_ankle_vertical /
        torso_length
    )

    shoulder_hip_ratio = (
        shoulder_hip_vertical /
        torso_length
    )

    # -----------------------------------------------------
    # 3D knee angle
    # -----------------------------------------------------

    knee_angle = calculate_knee_angle_3d(
        hip,
        knee,
        ankle
    )

    return {
        "knee_angle": knee_angle,
        "hip_knee_ratio": hip_knee_ratio,
        "knee_ankle_ratio": knee_ankle_ratio,
        "shoulder_hip_ratio": shoulder_hip_ratio
    }

# =========================================================
# CAMERA / SETUP VALIDATION
# =========================================================

SETUP_MIN_VISIBILITY = 0.40
SETUP_MIN_VISIBLE_LANDMARKS = 6

SETUP_LANDMARKS = [
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_HIP",
    "RIGHT_HIP",
    "LEFT_KNEE",
    "RIGHT_KNEE",
    "LEFT_ANKLE",
    "RIGHT_ANKLE",
]


def validate_setup(landmarks):
    """
    Checks whether the patient's major body landmarks
    are sufficiently visible for posture/exercise analysis.

    Returns:
        {
            "ready": True/False,
            "visible_count": int,
            "visibility_score": float,
            "message": str
        }
    """

    if landmarks is None:
        return {
            "ready": False,
            "visible_count": 0,
            "visibility_score": 0.0,
            "message": "No person detected"
        }

    visibility_values = []

    for name in SETUP_LANDMARKS:

        point = landmarks.get(name)

        if point is None:
            continue

        visibility = point.get(
            "visibility",
            0.0
        )

        visibility_values.append(
            visibility
        )

    visible_count = sum(
        visibility >= SETUP_MIN_VISIBILITY
        for visibility in visibility_values
    )

    if visibility_values:
        visibility_score = (
            sum(visibility_values)
            /
            len(visibility_values)
        )
    else:
        visibility_score = 0.0

    # -----------------------------------------------------
    # Basic readiness check
    # -----------------------------------------------------

    ready = (
        visible_count >=
        SETUP_MIN_VISIBLE_LANDMARKS
    )

    if ready:
        message = "SETUP OK"

    else:
        message = (
            "Please ensure full body is visible "
            "and lighting is adequate"
        )

    return {
        "ready": ready,
        "visible_count": visible_count,
        "visibility_score": visibility_score,
        "message": message
    }
# =========================================================
# SINGLE FRAME
# =========================================================

def estimate_posture(landmarks):

    left = analyse_side(
        landmarks,
        "left"
    )

    right = analyse_side(
        landmarks,
        "right"
    )

    valid = [
        result
        for result in (left, right)
        if result is not None
    ]

    if not valid:

        return {
            "posture": "UNKNOWN",
            "left_knee_angle": None,
            "right_knee_angle": None,
            "average_knee_angle": None,
            "left_hip_knee_ratio": None,
            "right_hip_knee_ratio": None,
            "average_hip_knee_ratio": None
        }

    # -----------------------------------------------------
    # Average bilateral features
    # -----------------------------------------------------

    angles = [
        result["knee_angle"]
        for result in valid
        if result["knee_angle"] is not None
    ]

    ratios = [
        result["hip_knee_ratio"]
        for result in valid
    ]

    average_angle = (
        sum(angles) / len(angles)
        if angles
        else None
    )

    average_ratio = (
        sum(ratios) / len(ratios)
        if ratios
        else None
    )

    # -----------------------------------------------------
    # Classification is handled by PostureDetector.
    # -----------------------------------------------------

    return {
        "posture": "UNKNOWN",

        "left_knee_angle": (
            left["knee_angle"]
            if left else None
        ),

        "right_knee_angle": (
            right["knee_angle"]
            if right else None
        ),

        "average_knee_angle": average_angle,

        "left_hip_knee_ratio": (
            left["hip_knee_ratio"]
            if left else None
        ),

        "right_hip_knee_ratio": (
            right["hip_knee_ratio"]
            if right else None
        ),

        "average_hip_knee_ratio": average_ratio
    }


# =========================================================
# TEMPORAL DETECTOR
# =========================================================

class PostureDetector:

    def __init__(
        self,
        smoothing_window=SMOOTHING_WINDOW,
        required_frames=REQUIRED_FRAMES
    ):

        self.angle_history = deque(
            maxlen=smoothing_window
        )

        self.ratio_history = deque(
            maxlen=smoothing_window
        )

        self.current_posture = "UNKNOWN"

        self.required_frames = required_frames

        self.standing_count = 0
        self.sitting_count = 0

    def update(self, landmarks):

        result = estimate_posture(
            landmarks
        )

        angle = result[
            "average_knee_angle"
        ]

        ratio = result[
            "average_hip_knee_ratio"
        ]

        # -------------------------------------------------
        # No reliable landmarks
        # -------------------------------------------------

        if ratio is None:

            return {
                **result,
                "posture": self.current_posture,
                "smoothed_knee_angle": None,
                "smoothed_hip_knee_ratio": None
            }

        # -------------------------------------------------
        # Store
        # -------------------------------------------------

        if angle is not None:
            self.angle_history.append(angle)

        self.ratio_history.append(ratio)

        # -------------------------------------------------
        # Smooth
        # -------------------------------------------------

        smooth_angle = (
            sum(self.angle_history)
            /
            len(self.angle_history)
            if self.angle_history
            else None
        )

        smooth_ratio = (
            sum(self.ratio_history)
            /
            len(self.ratio_history)
        )

        # =================================================
        # CLASSIFICATION
        # =================================================

        # The hip-knee ratio is the primary feature.
        #
        # Standing:
        #     ratio >= 0.50
        #
        # Sitting:
        #     ratio <= 0.40
        #
        # Between 0.40 and 0.50:
        #     uncertain transition region.
        #
        # Knee angle is intentionally NOT used for
        # classification.

        standing_condition = (
            smooth_ratio >=
            STANDING_RATIO_THRESHOLD
        )

        sitting_condition = (
            smooth_ratio <=
            SITTING_RATIO_THRESHOLD
        )

        # -------------------------------------------------
        # State machine
        # -------------------------------------------------

        if standing_condition:

            self.standing_count += 1
            self.sitting_count = 0

            if (
                self.standing_count
                >= self.required_frames
            ):

                self.current_posture = "STANDING"

                self.standing_count = 0

        elif sitting_condition:

            self.sitting_count += 1
            self.standing_count = 0

            if (
                self.sitting_count
                >= self.required_frames
            ):

                self.current_posture = "SITTING"

                self.sitting_count = 0

        else:

            # Transition / uncertain region.
            #
            # Keep the previous confirmed posture
            # instead of flickering to UNKNOWN.

            self.standing_count = 0
            self.sitting_count = 0

        return {
            **result,
            "posture": self.current_posture,
            "smoothed_knee_angle": smooth_angle,
            "smoothed_hip_knee_ratio": smooth_ratio
        }

    def reset(self):

        self.angle_history.clear()
        self.ratio_history.clear()

        self.current_posture = "UNKNOWN"

        self.standing_count = 0
        self.sitting_count = 0


# =========================================================
# LIVE DETECTOR
# =========================================================

_default_detector = PostureDetector()


def detect_posture(landmarks):

    result = _default_detector.update(
        landmarks
    )

    return result["posture"]