from rehabilitation.data_filter import (
    is_valid_measurement,
    get_valid_angle
)


def test_valid_measurement():
    assert is_valid_measurement(120, 0.9) is True


def test_low_visibility():
    assert is_valid_measurement(120, 0.2) is False


def test_missing_angle():
    assert is_valid_measurement(None, 0.9) is False


def test_missing_visibility():
    assert is_valid_measurement(120, None) is False


def test_boundary_visibility():
    assert is_valid_measurement(120, 0.5) is True


def create_valid_pose_frame():
    return {
        "angles": {
            "left_elbow": 120
        },
        "visibility": {
            "LEFT_SHOULDER": 0.9,
            "LEFT_ELBOW": 0.95,
            "LEFT_WRIST": 0.9
        }
    }


def test_get_valid_angle():
    pose_frame = create_valid_pose_frame()

    result = get_valid_angle(
        pose_frame,
        "left_elbow"
    )

    assert result == 120


def test_get_valid_angle_rejects_low_visibility():
    pose_frame = create_valid_pose_frame()

    pose_frame["visibility"]["LEFT_WRIST"] = 0.2

    result = get_valid_angle(
        pose_frame,
        "left_elbow"
    )

    assert result is None


def test_get_valid_angle_missing_pose_frame():
    result = get_valid_angle(
        None,
        "left_elbow"
    )

    assert result is None


def test_unknown_angle():
    pose_frame = create_valid_pose_frame()

    try:
        get_valid_angle(
            pose_frame,
            "unknown_angle"
        )
        assert False
    except ValueError:
        assert True