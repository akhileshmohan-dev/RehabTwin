from rehabilitation.session_assessment import SessionAssessment


def test_session_assessment_returns_quality():
    assessment = SessionAssessment()

    result = assessment.assess(
        exercise="elbow_flexion",
        angle_history=[
            170, 160, 140, 120, 100,
            80, 60, 40, 60, 80,
            110, 140, 165, 170
        ],
        repetitions=3,
    )

    assert result["movement_quality"] in {
        "GOOD",
        "MODERATE",
        "POOR",
    }


def test_empty_session_returns_no_quality():
    assessment = SessionAssessment()

    result = assessment.assess(
        exercise="elbow_flexion",
        angle_history=[],
        repetitions=0,
    )

    assert result["movement_quality"] is None