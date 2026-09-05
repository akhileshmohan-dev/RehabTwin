from rehabilitation.data_filter import get_valid_angle
from rehabilitation.smoothing import MovingAverageFilter
from rehabilitation.repetition_counter import RepetitionCounter
from rehabilitation.rom_calculator import calculate_rom
from rehabilitation.exercise_config import EXERCISE_CONFIG


class RehabilitationAnalysisPipeline:

    def __init__(
        self,
        exercise="elbow_flexion",
        side="left",
        smoothing_window=5,
        flexed_threshold=None,
        extended_threshold=None,
    ):
        if exercise not in EXERCISE_CONFIG:
            raise ValueError(
                f"Unsupported exercise: {exercise}"
            )

        if side not in ("left", "right"):
            raise ValueError(
                "side must be 'left' or 'right'"
            )

        config = EXERCISE_CONFIG[exercise]
        side_config = config[side]

        self.exercise = exercise
        self.side = side
        self.angle_name = side_config["angle_name"]

        self.smoother = MovingAverageFilter(
            window_size=smoothing_window
        )

        self.counter = RepetitionCounter(
            flexed_threshold=(
                flexed_threshold
                if flexed_threshold is not None
                else config["flexed_threshold"]
            ),
            extended_threshold=(
                extended_threshold
                if extended_threshold is not None
                else config["extended_threshold"]
            ),
        )

        self.angle_history = []

    def process(self, pose_frame):

        if pose_frame is None:
            return {
                "raw_angle": None,
                "valid_angle": None,
                "smoothed_angle": None,
                "state": self.counter.state,
                "repetitions": self.counter.repetitions,
                "rom": calculate_rom(self.angle_history),
            }

        angles = pose_frame.get("angles") or {}

        raw_angle = angles.get(self.angle_name)

        valid_angle = get_valid_angle(
            pose_frame,
            self.angle_name
        )

        smoothed_angle = self.smoother.update(
            valid_angle
        )

        if smoothed_angle is not None:
            self.angle_history.append(
                smoothed_angle
            )

        counter_result = self.counter.update(
            smoothed_angle
        )

        rom_result = calculate_rom(
            self.angle_history
        )

        return {
            "raw_angle": raw_angle,
            "valid_angle": valid_angle,
            "smoothed_angle": smoothed_angle,
            "state": counter_result["state"],
            "repetitions": counter_result["repetitions"],
            "rom": rom_result,
        }

    def reset(self):
        """Reset smoothing, repetition, and ROM state."""

        self.smoother.reset()

        self.counter.state = "UNKNOWN"
        self.counter.repetitions = 0

        self.angle_history.clear()


# Temporary compatibility with existing tests/code
ElbowAnalysisPipeline = RehabilitationAnalysisPipeline