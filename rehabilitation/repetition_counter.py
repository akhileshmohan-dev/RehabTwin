class RepetitionCounter:
    """
    State-machine based repetition counter.

    A repetition is counted when the joint moves through:

        EXTENDED -> FLEXED -> EXTENDED

    The counter uses two thresholds (hysteresis) to reduce
    false transitions caused by small angle fluctuations.
    """

    def __init__(self, flexed_threshold=100, extended_threshold=160):
        if flexed_threshold >= extended_threshold:
            raise ValueError(
                "flexed_threshold must be smaller than extended_threshold"
            )

        self.flexed_threshold = flexed_threshold
        self.extended_threshold = extended_threshold

        self.state = "UNKNOWN"
        self.repetitions = 0

    def update(self, angle):
        """
        Update the counter with one joint-angle measurement.

        Parameters
        ----------
        angle : float
            Joint angle in degrees.

        Returns
        -------
        dict
            Current state and repetition count.
        """

        if angle is None:
            return {
                "state": self.state,
                "repetitions": self.repetitions
            }

        if self.state == "UNKNOWN":
            if angle >= self.extended_threshold:
                self.state = "EXTENDED"

        elif self.state == "EXTENDED":
            if angle <= self.flexed_threshold:
                self.state = "FLEXED"

        elif self.state == "FLEXED":
            if angle >= self.extended_threshold:
                self.state = "EXTENDED"
                self.repetitions += 1

        return {
            "state": self.state,
            "repetitions": self.repetitions
        }