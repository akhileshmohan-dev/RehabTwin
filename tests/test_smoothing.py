from rehabilitation.smoothing import MovingAverageFilter


def test_moving_average():
    smoother = MovingAverageFilter(window_size=3)

    assert smoother.update(90) == 90
    assert smoother.update(100) == 95
    assert smoother.update(110) == 100


def test_window_moves_forward():
    smoother = MovingAverageFilter(window_size=3)

    smoother.update(90)
    smoother.update(100)
    smoother.update(110)

    result = smoother.update(120)

    assert result == 110


def test_none_input():
    smoother = MovingAverageFilter(window_size=3)

    assert smoother.update(None) is None


def test_reset():
    smoother = MovingAverageFilter(window_size=3)

    smoother.update(90)
    smoother.update(100)

    smoother.reset()

    assert smoother.update(120) == 120


def test_invalid_window_size():
    try:
        MovingAverageFilter(window_size=0)
        assert False
    except ValueError:
        assert True