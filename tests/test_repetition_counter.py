from rehabilitation.repetition_counter import RepetitionCounter


def test_one_complete_rep():
    counter = RepetitionCounter(
        flexed_threshold=100,
        extended_threshold=160
    )

    for angle in [170, 140, 90, 120, 170]:
        counter.update(angle)

    assert counter.repetitions == 1


def test_two_complete_reps():
    counter = RepetitionCounter(
        flexed_threshold=100,
        extended_threshold=160
    )

    for angle in [170, 90, 170, 90, 170]:
        counter.update(angle)

    assert counter.repetitions == 2


def test_incomplete_rep_not_counted():
    counter = RepetitionCounter(
        flexed_threshold=100,
        extended_threshold=160
    )

    for angle in [170, 120, 130, 170]:
        counter.update(angle)

    assert counter.repetitions == 0


def test_noise_around_extended_threshold():
    counter = RepetitionCounter(
        flexed_threshold=100,
        extended_threshold=160
    )

    for angle in [170, 158, 162, 157, 165]:
        counter.update(angle)

    assert counter.repetitions == 0


def test_noise_while_flexed():
    counter = RepetitionCounter(
        flexed_threshold=100,
        extended_threshold=160
    )

    for angle in [170, 100, 98, 102, 95, 170]:
        counter.update(angle)

    assert counter.repetitions == 1


def test_starting_flexed_does_not_count_rep():
    counter = RepetitionCounter(
        flexed_threshold=100,
        extended_threshold=160
    )

    for angle in [90, 120, 160, 170]:
        counter.update(angle)

    assert counter.repetitions == 0