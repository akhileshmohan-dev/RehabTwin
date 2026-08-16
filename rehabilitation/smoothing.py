from collections import deque


class MovingAverageFilter:
    """
    Simple moving-average filter for joint-angle measurements.

    The filter averages the most recent `window_size` valid
    measurements to reduce small frame-to-frame fluctuations.
    """

    def __init__(self, window_size=5):
        if window_size <= 0:
            raise ValueError("window_size must be greater than 0")

        self.window_size = window_size
        self.values = deque(maxlen=window_size)

    def update(self, value):
        """
        Add a new measurement and return the smoothed value.

        Returns None if the input value is None.
        """

        if value is None:
            return None

        self.values.append(value)

        return sum(self.values) / len(self.values)

    def reset(self):
        """Clear all stored measurements."""
        self.values.clear()