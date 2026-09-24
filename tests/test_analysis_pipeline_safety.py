"""
tests/test_analysis_pipeline_safety.py

Unit tests verifying the Repetition & ROM Safety Invariants and
entry-point validation consistency for Phase 5B.

Strict Rules:
1. INVALID POSE FRAME
   -> status/exception is reported
   -> rehabilitation metrics (repetitions, state, angle_history, ROM) are NOT updated.
2. Centralized PoseValidator is the single authoritative validation logic
   regardless of whether process() or process_landmarks() is called.
"""
from rehabilitation.exercises import get_exercise_definition
from rehabilitation.analysis_pipeline import GenericAnalysisPipeline


def _make_valid_frame(angle, side="left"):
    return {
        "angles": {f"{side}_elbow": angle},
        "visibility": {
            f"{side.upper()}_SHOULDER": 0.95,
            f"{side.upper()}_ELBOW": 0.95,
            f"{side.upper()}_WRIST": 0.95,
        },
        "landmarks": {},
    }


def _make_invalid_frame(angle=90.0, side="left"):
    return {
        "angles": {f"{side}_elbow": angle},
        "visibility": {
            f"{side.upper()}_SHOULDER": 0.95,
            f"{side.upper()}_ELBOW": 0.20,  # low visibility!
            f"{side.upper()}_WRIST": 0.95,
        },
        "landmarks": {},
    }


# ===========================================================================
# A. process() with a valid pose -> same result as before
# ===========================================================================

def test_process_valid_pose_matches_expected():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    valid_frame = {
        "landmarks": {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "visibility": 0.99},
            "LEFT_WRIST": {"x": 500.0, "y": 500.0, "visibility": 0.99},
        }
    }
    res = pipeline.process(valid_frame)
    assert res["pose_validation"]["is_valid"] is True
    assert res["pose_validation"]["status"] == "VALID"
    assert res["raw_angle"] is not None
    assert abs(res["raw_angle"] - 90.0) < 1.0
    assert res["valid_angle"] == res["raw_angle"]
    assert res["smoothed_angle"] == res["raw_angle"]
    assert len(pipeline.angle_history) == 1


# ===========================================================================
# B. process() with missing required landmarks -> REQUIRED_LANDMARKS_MISSING
# ===========================================================================

def test_process_missing_required_landmarks():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    frame = {
        "landmarks": {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "visibility": 0.99},
            # LEFT_WRIST is missing!
        }
    }
    res = pipeline.process(frame)
    assert res["pose_validation"]["is_valid"] is False
    assert res["pose_validation"]["status"] == "REQUIRED_LANDMARKS_MISSING"
    assert "LEFT_WRIST" in res["pose_validation"]["missing_landmarks"]
    assert res["valid_angle"] is None
    assert res["smoothed_angle"] is None
    assert len(pipeline.angle_history) == 0


# ===========================================================================
# C. process() with low visibility -> LOW_VISIBILITY
# ===========================================================================

def test_process_low_visibility():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    frame = {
        "landmarks": {
            "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "visibility": 0.20},  # Low visibility!
            "LEFT_WRIST": {"x": 500.0, "y": 500.0, "visibility": 0.99},
        }
    }
    res = pipeline.process(frame)
    assert res["pose_validation"]["is_valid"] is False
    assert res["pose_validation"]["status"] == "LOW_VISIBILITY"
    assert "LEFT_ELBOW" in res["pose_validation"]["low_visibility_landmarks"]
    assert res["valid_angle"] is None
    assert res["smoothed_angle"] is None
    assert len(pipeline.angle_history) == 0


# ===========================================================================
# D. process() with degenerate/invalid coordinates -> INVALID_ANGLE
# ===========================================================================

def test_process_degenerate_invalid_coordinates():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    # 1. Degenerate overlapping points
    degenerate_frame = {
        "landmarks": {
            "LEFT_SHOULDER": {"x": 300.0, "y": 500.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "visibility": 0.99},  # Same point as shoulder!
            "LEFT_WRIST": {"x": 500.0, "y": 500.0, "visibility": 0.99},
        }
    }
    res_deg = pipeline.process(degenerate_frame)
    assert res_deg["pose_validation"]["is_valid"] is False
    assert res_deg["pose_validation"]["status"] == "INVALID_ANGLE"
    assert res_deg["valid_angle"] is None
    assert len(pipeline.angle_history) == 0

    # 2. NaN coordinates
    nan_frame = {
        "landmarks": {
            "LEFT_SHOULDER": {"x": float("nan"), "y": 200.0, "visibility": 0.99},
            "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "visibility": 0.99},
            "LEFT_WRIST": {"x": 500.0, "y": 500.0, "visibility": 0.99},
        }
    }
    res_nan = pipeline.process(nan_frame)
    assert res_nan["pose_validation"]["is_valid"] is False
    assert res_nan["pose_validation"]["status"] == "INVALID_ANGLE"
    assert res_nan["valid_angle"] is None
    assert len(pipeline.angle_history) == 0


# ===========================================================================
# E. Invalid frames do not change repetitions, state, angle_history, ROM
# ===========================================================================

def test_invalid_frames_do_not_increment_reps():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    for _ in range(10):
        res = pipeline.process(None)
        assert res["repetitions"] == 0
        assert res["state"] == "UNKNOWN"
        assert res["valid_angle"] is None

    for _ in range(10):
        res = pipeline.process(_make_invalid_frame(angle=80.0))
        assert res["repetitions"] == 0
        assert res["state"] == "UNKNOWN"
        assert res["valid_angle"] is None
        assert res["pose_validation"]["status"] == "LOW_VISIBILITY"

    assert len(pipeline.angle_history) == 0


def test_invalid_frames_do_not_corrupt_rom():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    # Establish 1 rep with valid frames
    for _ in range(5):
        pipeline.process(_make_valid_frame(170.0))
    for _ in range(5):
        pipeline.process(_make_valid_frame(85.0))
    for _ in range(5):
        baseline = pipeline.process(_make_valid_frame(170.0))

    assert baseline["repetitions"] == 1
    assert baseline["state"] == "EXTENDED"
    base_rom = baseline["rom"]
    assert base_rom["min_angle"] is not None
    assert base_rom["max_angle"] is not None
    assert base_rom["rom"] is not None
    history_len = len(pipeline.angle_history)

    # Feed 15 invalid frames (low visibility, corrupt data)
    for _ in range(15):
        corrupt_frame = _make_invalid_frame(angle=10.0)
        res = pipeline.process(corrupt_frame)
        assert res["repetitions"] == 1
        assert res["state"] == "EXTENDED"
        assert res["rom"]["min_angle"] == base_rom["min_angle"]
        assert res["rom"]["max_angle"] == base_rom["max_angle"]
        assert res["rom"]["rom"] == base_rom["rom"]
        assert len(pipeline.angle_history) == history_len


# ===========================================================================
# F. Invalid -> valid recovery still works
# ===========================================================================

def test_recovery_from_invalid_to_valid():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    # Start extended
    for _ in range(5):
        pipeline.process(_make_valid_frame(170.0))
    assert pipeline.counter.state == "EXTENDED"

    # Flex to 90 deg
    for _ in range(5):
        pipeline.process(_make_valid_frame(90.0))
    assert pipeline.counter.state == "FLEXED"

    # Interleave 10 invalid frames (e.g. obscured view)
    for _ in range(10):
        res = pipeline.process(None)
        assert res["state"] == "FLEXED"
        assert res["repetitions"] == 0

    # Resume valid extension to 170 deg
    res_final = None
    for _ in range(5):
        res_final = pipeline.process(_make_valid_frame(170.0))

    assert res_final["repetitions"] == 1
    assert res_final["state"] == "EXTENDED"


# ===========================================================================
# G. Both left and right sides remain correct
# ===========================================================================

def test_bilateral_process_left_and_right():
    # Left side
    left_def = get_exercise_definition("knee_flexion", side="left")
    pipeline_l = GenericAnalysisPipeline(left_def)
    left_frame = {
        "landmarks": {
            "LEFT_HIP": {"x": 300.0, "y": 800.0, "visibility": 0.99},
            "LEFT_KNEE": {"x": 300.0, "y": 1100.0, "visibility": 0.99},
            "LEFT_ANKLE": {"x": 450.0, "y": 1100.0, "visibility": 0.99},
        }
    }
    res_l = pipeline_l.process(left_frame)
    assert res_l["pose_validation"]["is_valid"] is True
    assert res_l["pose_validation"]["status"] == "VALID"
    assert res_l["valid_angle"] is not None

    # Right side
    right_def = get_exercise_definition("knee_flexion", side="right")
    pipeline_r = GenericAnalysisPipeline(right_def)
    right_frame = {
        "landmarks": {
            "RIGHT_HIP": {"x": 700.0, "y": 800.0, "visibility": 0.99},
            "RIGHT_KNEE": {"x": 700.0, "y": 1100.0, "visibility": 0.99},
            "RIGHT_ANKLE": {"x": 850.0, "y": 1100.0, "visibility": 0.99},
        }
    }
    res_r = pipeline_r.process(right_frame)
    assert res_r["pose_validation"]["is_valid"] is True
    assert res_r["pose_validation"]["status"] == "VALID"
    assert res_r["valid_angle"] is not None

    # Passing left landmarks to right-side pipeline flags missing right landmarks
    res_mismatch = pipeline_r.process(left_frame)
    assert res_mismatch["pose_validation"]["is_valid"] is False
    assert res_mismatch["pose_validation"]["status"] == "REQUIRED_LANDMARKS_MISSING"
    assert "RIGHT_HIP" in res_mismatch["pose_validation"]["missing_landmarks"]


# ===========================================================================
# Consistency: process_landmarks() behaves identically to process()
# ===========================================================================

def test_process_landmarks_safety_and_consistency():
    ex_def = get_exercise_definition("elbow_flexion", side="left")
    pipeline = GenericAnalysisPipeline(ex_def)

    # 1. Landmarks is None
    res = pipeline.process_landmarks(None)
    assert res["pose_validation"]["is_valid"] is False
    assert res["pose_validation"]["status"] == "NO_PERSON_DETECTED"
    assert res["valid_angle"] is None
    assert res["repetitions"] == 0

    # 2. Landmarks missing wrist
    missing_lm = {
        "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
        "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
    }
    res_missing = pipeline.process_landmarks(missing_lm)
    assert res_missing["pose_validation"]["is_valid"] is False
    assert res_missing["pose_validation"]["status"] == "REQUIRED_LANDMARKS_MISSING"
    assert "LEFT_WRIST" in res_missing["pose_validation"]["missing_landmarks"]
    assert res_missing["valid_angle"] is None

    # 3. Valid landmarks
    valid_lm = {
        "LEFT_SHOULDER": {"x": 300.0, "y": 200.0, "z": 0.0, "visibility": 0.99},
        "LEFT_ELBOW": {"x": 300.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
        "LEFT_WRIST": {"x": 500.0, "y": 500.0, "z": 0.0, "visibility": 0.99},
    }
    res_valid = pipeline.process_landmarks(valid_lm)
    assert res_valid["pose_validation"]["is_valid"] is True
    assert res_valid["pose_validation"]["status"] == "VALID"
    assert res_valid["valid_angle"] is not None
