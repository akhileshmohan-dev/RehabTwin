from pathlib import Path

from digital_thread.thread import DigitalThread


def test_sqlite_thread(tmp_path: Path):
    db_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    thread = DigitalThread(db_url)
    sid = thread.start_session("P001", "elbow_flexion")

    for i in range(3):
        thread.record_frame(
            frame_id=i,
            landmarks={"left_elbow": {"x": 0.5, "y": 0.4, "visibility": 0.99}},
            joint_angles={"left_elbow": 130.0 - i},
            phase="CONCENTRIC",
        )

    thread.record_result(12, 48.0, 142.0, 94.0, 87.0, "Good consistency.")
    thread.end_session()

    session = thread.get_session(sid)
    assert session["status"] == "COMPLETED"
    assert thread.history("P001")[0]["results"][0]["repetitions"] == 12
