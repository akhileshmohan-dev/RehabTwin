"""
RehabTwin Pose Validator

Controls whether a MediaPipe pose is trustworthy enough to
enter the rehabilitation pipeline.

States:

    WAITING
        Looking for a complete and sufficiently visible pose.

    READY
        A complete pose has been stable for the required number
        of consecutive frames.

    TRACKING
        Valid poses are being accepted and recorded.

    HOLDING
        A temporary bad frame occurred. The last valid pose should
        be held downstream rather than replacing it with bad data.

    LOST
        Tracking has remained invalid for too long. The system must
        reacquire a complete stable pose before recording resumes.

Important:

    Large BODY movement is NOT treated as invalid.

The user may legitimately move closer/further from the camera,
raise their arms, bend, squat, etc.

We therefore do NOT use a crude "whole body moved too much"
threshold here.

The current validation rules are:

    1. MediaPipe pose exists.
    2. Exactly 33 landmarks exist.
    3. All 33 landmarks meet the visibility threshold.
    4. A new tracking session requires several consecutive
       valid frames.

During an already-active tracking session, a temporary bad frame
does not immediately destroy tracking. It enters HOLDING first.
"""


import mediapipe as mp


# ---------------------------------------------------------------------
# MediaPipe Pose
# ---------------------------------------------------------------------

mp_pose = mp.solutions.pose


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

EXPECTED_LANDMARK_COUNT = 33


# ---------------------------------------------------------------------
# Tracking states
# ---------------------------------------------------------------------

WAITING = "WAITING"
READY = "READY"
TRACKING = "TRACKING"
HOLDING = "HOLDING"
LOST = "LOST"


# ---------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------

class PoseValidationResult:
    """
    Result produced for every MediaPipe frame.
    """

    def __init__(
        self,
        valid=False,
        landmark_count=0,
        visible_count=0,
        reason="",
        state=WAITING,
        consecutive_valid_frames=0,
        consecutive_invalid_frames=0,
        tracking_ready=False,
        should_accept=False
    ):
        self.valid = valid

        self.landmark_count = (
            landmark_count
        )

        self.visible_count = (
            visible_count
        )

        self.reason = reason

        self.state = state

        self.consecutive_valid_frames = (
            consecutive_valid_frames
        )

        self.consecutive_invalid_frames = (
            consecutive_invalid_frames
        )

        self.tracking_ready = (
            tracking_ready
        )

        self.should_accept = (
            should_accept
        )


# ---------------------------------------------------------------------
# Pose Validator
# ---------------------------------------------------------------------

class PoseValidator:
    """
    Full-body pose acquisition and tracking gate.

    The validator deliberately separates:

        "Is this frame valid?"

    from:

        "Is the tracking session established?"

    This allows us to tolerate occasional bad frames without
    allowing bad data into the recording pipeline.
    """

    def __init__(
        self,
        min_visibility=0.5,
        required_stable_frames=5,
        max_invalid_frames=10
    ):
        self.min_visibility = (
            min_visibility
        )

        self.required_stable_frames = (
            required_stable_frames
        )

        self.max_invalid_frames = (
            max_invalid_frames
        )

        self.state = WAITING

        self.consecutive_valid_frames = 0

        self.consecutive_invalid_frames = 0

        self.total_valid_frames = 0

        self.total_invalid_frames = 0

        self.last_result = (
            PoseValidationResult()
        )

    # -----------------------------------------------------------------
    # Validate a MediaPipe frame
    # -----------------------------------------------------------------

    def validate(self, results):
        """
        Validate one MediaPipe frame and update the tracking state.

        Returns:
            PoseValidationResult
        """

        # -------------------------------------------------------------
        # Check basic pose validity
        # -------------------------------------------------------------

        valid, landmark_count, visible_count, reason = (
            self._check_frame(results)
        )

        # =============================================================
        # VALID FRAME
        # =============================================================

        if valid:

            self.total_valid_frames += 1

            self.consecutive_valid_frames += 1

            self.consecutive_invalid_frames = 0

            # ---------------------------------------------------------
            # WAITING / LOST
            #
            # Need a sequence of stable valid frames before tracking
            # is allowed to begin again.
            # ---------------------------------------------------------

            if self.state in (
                WAITING,
                LOST
            ):

                if (
                    self.consecutive_valid_frames
                    >= self.required_stable_frames
                ):

                    self.state = TRACKING

                else:

                    self.state = WAITING

            # ---------------------------------------------------------
            # HOLDING
            #
            # A valid frame has returned.
            # Resume tracking immediately because the previous
            # tracking session has not necessarily been lost.
            # ---------------------------------------------------------

            elif self.state == HOLDING:

                self.state = TRACKING

            # ---------------------------------------------------------
            # Already tracking
            # ---------------------------------------------------------

            elif self.state == TRACKING:

                self.state = TRACKING

            # ---------------------------------------------------------
            # READY is treated as tracking once valid data continues.
            # ---------------------------------------------------------

            elif self.state == READY:

                self.state = TRACKING

            # ---------------------------------------------------------
            # Should this frame be accepted?
            #
            # Only accept frames after acquisition is complete.
            # ---------------------------------------------------------

            should_accept = (
                self.state == TRACKING
            )

            result = PoseValidationResult(
                valid=True,
                landmark_count=landmark_count,
                visible_count=visible_count,
                reason="VALID",
                state=self.state,
                consecutive_valid_frames=(
                    self.consecutive_valid_frames
                ),
                consecutive_invalid_frames=(
                    self.consecutive_invalid_frames
                ),
                tracking_ready=(
                    self.state == TRACKING
                ),
                should_accept=should_accept
            )

            self.last_result = result

            return result

        # =============================================================
        # INVALID FRAME
        # =============================================================

        self.total_invalid_frames += 1

        self.consecutive_invalid_frames += 1

        self.consecutive_valid_frames = 0

        # -------------------------------------------------------------
        # Before acquisition
        # -------------------------------------------------------------

        if self.state in (
            WAITING,
            READY,
            LOST
        ):

            self.state = WAITING

        # -------------------------------------------------------------
        # Temporary tracking loss
        # -------------------------------------------------------------

        elif self.state == TRACKING:

            self.state = HOLDING

        # -------------------------------------------------------------
        # Already holding
        # -------------------------------------------------------------

        elif self.state == HOLDING:

            if (
                self.consecutive_invalid_frames
                >= self.max_invalid_frames
            ):

                self.state = LOST

        result = PoseValidationResult(
            valid=False,
            landmark_count=landmark_count,
            visible_count=visible_count,
            reason=reason,
            state=self.state,
            consecutive_valid_frames=(
                self.consecutive_valid_frames
            ),
            consecutive_invalid_frames=(
                self.consecutive_invalid_frames
            ),
            tracking_ready=False,
            should_accept=False
        )

        self.last_result = result

        return result

    # -----------------------------------------------------------------
    # Reset
    # -----------------------------------------------------------------

    def reset(self):
        """
        Completely reset tracking acquisition.
        """

        self.state = WAITING

        self.consecutive_valid_frames = 0

        self.consecutive_invalid_frames = 0

        self.total_valid_frames = 0

        self.total_invalid_frames = 0

        self.last_result = (
            PoseValidationResult()
        )

    # -----------------------------------------------------------------
    # Check one frame
    # -----------------------------------------------------------------

    def _check_frame(self, results):
        """
        Perform structural and visibility checks.

        Returns:

            (
                valid,
                landmark_count,
                visible_count,
                reason
            )
        """

        # -------------------------------------------------------------
        # No results
        # -------------------------------------------------------------

        if results is None:

            return (
                False,
                0,
                0,
                "NO_RESULTS"
            )

        # -------------------------------------------------------------
        # No pose
        # -------------------------------------------------------------

        if not results.pose_landmarks:

            return (
                False,
                0,
                0,
                "NO_POSE"
            )

        landmarks = (
            results.pose_landmarks.landmark
        )

        landmark_count = len(
            landmarks
        )

        # -------------------------------------------------------------
        # All 33 landmarks must exist
        # -------------------------------------------------------------

        if (
            landmark_count
            != EXPECTED_LANDMARK_COUNT
        ):

            return (
                False,
                landmark_count,
                0,
                "INCOMPLETE_LANDMARKS"
            )

        # -------------------------------------------------------------
        # Visibility
        # -------------------------------------------------------------

        visible_count = 0

        for landmark in landmarks:

            if landmark.visibility >= self.min_visibility:

                visible_count += 1

        # -------------------------------------------------------------
        # Every landmark must satisfy visibility threshold
        # -------------------------------------------------------------

        if (
            visible_count
            != EXPECTED_LANDMARK_COUNT
        ):

            return (
                False,
                landmark_count,
                visible_count,
                "LOW_VISIBILITY"
            )

        # -------------------------------------------------------------
        # Everything passed
        # -------------------------------------------------------------

        return (
            True,
            landmark_count,
            visible_count,
            "VALID"
        )

    # -----------------------------------------------------------------
    # Debug string
    # -----------------------------------------------------------------

    def debug_string(self):
        """
        Return a compact human-readable validator status.
        """

        result = self.last_result

        return (
            f"POSE | "
            f"state={result.state} | "
            f"landmarks="
            f"{result.landmark_count}/33 | "
            f"visible="
            f"{result.visible_count}/33 | "
            f"valid="
            f"{result.valid} | "
            f"accepted="
            f"{result.should_accept} | "
            f"valid_streak="
            f"{result.consecutive_valid_frames}/"
            f"{self.required_stable_frames} | "
            f"invalid_streak="
            f"{result.consecutive_invalid_frames}/"
            f"{self.max_invalid_frames} | "
            f"reason="
            f"{result.reason}"
        )