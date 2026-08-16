from rehabilitation.analysis_pipeline import ElbowAnalysisPipeline


def create_pose_frame(angle):
    return {
        "angles": {
            "left_elbow": angle
        },
        "visibility": {
            "LEFT_SHOULDER": 0.9,
            "LEFT_ELBOW": 0.9,
            "LEFT_WRIST": 0.9,
        },
        "landmarks": {},
    }


def feed_angle(pipeline, angle, frames=5):
    result = None

    for _ in range(frames):
        result = pipeline.process(
            create_pose_frame(angle)
        )

    return result


def test_pipeline_returns_angle():
    pipeline = ElbowAnalysisPipeline()

    result = pipeline.process(
        create_pose_frame(170)
    )

    assert result["raw_angle"] == 170
    assert result["valid_angle"] == 170
    assert result["smoothed_angle"] == 170


def test_pipeline_counts_one_rep():
    pipeline = ElbowAnalysisPipeline()

    feed_angle(pipeline, 170)
    feed_angle(pipeline, 90)
    result = feed_angle(pipeline, 170)

    assert result["repetitions"] == 1
    assert result["state"] == "EXTENDED"


def test_pipeline_rejects_low_visibility():
    pipeline = ElbowAnalysisPipeline()

    pose_frame = create_pose_frame(90)
    pose_frame["visibility"]["LEFT_WRIST"] = 0.2

    result = pipeline.process(pose_frame)

    assert result["valid_angle"] is None
    assert result["smoothed_angle"] is None


def test_pipeline_multiple_reps():
    pipeline = ElbowAnalysisPipeline()

    feed_angle(pipeline, 170)

    feed_angle(pipeline, 90)
    feed_angle(pipeline, 170)

    feed_angle(pipeline, 90)
    feed_angle(pipeline, 170)

    feed_angle(pipeline, 90)
    result = feed_angle(pipeline, 170)

    assert result["repetitions"] == 3


def test_pipeline_reset():
    pipeline = ElbowAnalysisPipeline()

    feed_angle(pipeline, 170)
    feed_angle(pipeline, 90)
    feed_angle(pipeline, 170)

    assert pipeline.counter.repetitions == 1

    pipeline.reset()

    assert pipeline.counter.repetitions == 0
    assert pipeline.counter.state == "UNKNOWN"


def test_pipeline_calculates_rom():
    pipeline = ElbowAnalysisPipeline()

    feed_angle(pipeline, 170)
    feed_angle(pipeline, 90)
    feed_angle(pipeline, 170)

    result = pipeline.process(
        create_pose_frame(170)
    )

    assert result["rom"]["min_angle"] < 100
    assert result["rom"]["max_angle"] > 160
    assert result["rom"]["rom"] > 60


def test_pipeline_rom_empty():
    pipeline = ElbowAnalysisPipeline()

    result = pipeline.process(None)

    assert result["rom"]["min_angle"] is None
    assert result["rom"]["max_angle"] is None
    assert result["rom"]["rom"] is None


def test_pipeline_reset_clears_rom():
    pipeline = ElbowAnalysisPipeline()

    feed_angle(pipeline, 170)
    feed_angle(pipeline, 90)

    assert pipeline.angle_history

    pipeline.reset()

    assert pipeline.angle_history == []