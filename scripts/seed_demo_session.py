"""
Seed a synthetic COMPLETED rehabilitation session for 3D replay development.

No camera required. Generates ~10 seconds at 10 FPS of geometric movement for
one of the four approved exercises, populating all 33 MediaPipe landmark names
so the relevant limb visibly moves. Landmarks are persisted in pixel
coordinates together with the analysed image dimensions (matching the live
WebSocket pipeline), so GET /api/sessions/{id}/frames can normalize them.

Usage:
    python scripts/seed_demo_session.py
    python scripts/seed_demo_session.py --exercise knee_flexion --side right

Requires only structured telemetry; never writes images or video to disk.
"""
import argparse
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

# Ensure the repository root is importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.dependencies import (
    get_patient_repo,
    get_session_repo,
    get_telemetry_repo,
    get_result_repo,
)
from backend.schemas.session import StartSessionRequest, RecordResultRequest
from backend.services.session_service import SessionService
from digital_thread.models import utc_now
from pose_estimation.angle_utils import calculate_angle
from rehabilitation.exercises import get_exercise_definition

PATIENT_ID = "DEMO_001"
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
FPS = 10
DURATION_S = 10.0
REPETITIONS = 5
NOTES_TAG = "SYNTHETIC DEMO"

# Canonical MediaPipe Pose landmark names (33), left-oriented neutral base pose.
BASE_LANDMARKS = {
    "NOSE": (0.50, 0.10),
    "LEFT_EYE_INNER": (0.52, 0.08),
    "LEFT_EYE": (0.53, 0.08),
    "LEFT_EYE_OUTER": (0.54, 0.08),
    "RIGHT_EYE_INNER": (0.48, 0.08),
    "RIGHT_EYE": (0.47, 0.08),
    "RIGHT_EYE_OUTER": (0.46, 0.08),
    "LEFT_EAR": (0.56, 0.09),
    "RIGHT_EAR": (0.44, 0.09),
    "MOUTH_LEFT": (0.52, 0.12),
    "MOUTH_RIGHT": (0.48, 0.12),
    "LEFT_SHOULDER": (0.44, 0.26),
    "RIGHT_SHOULDER": (0.56, 0.26),
    "LEFT_ELBOW": (0.40, 0.42),
    "RIGHT_ELBOW": (0.60, 0.42),
    "LEFT_WRIST": (0.40, 0.58),
    "RIGHT_WRIST": (0.60, 0.58),
    "LEFT_PINKY": (0.39, 0.62),
    "RIGHT_PINKY": (0.61, 0.62),
    "LEFT_INDEX": (0.39, 0.63),
    "RIGHT_INDEX": (0.61, 0.63),
    "LEFT_THUMB": (0.41, 0.62),
    "RIGHT_THUMB": (0.59, 0.62),
    "LEFT_HIP": (0.44, 0.55),
    "RIGHT_HIP": (0.56, 0.55),
    "LEFT_KNEE": (0.44, 0.72),
    "RIGHT_KNEE": (0.56, 0.72),
    "LEFT_ANKLE": (0.44, 0.90),
    "RIGHT_ANKLE": (0.56, 0.90),
    "LEFT_HEEL": (0.45, 0.93),
    "RIGHT_HEEL": (0.55, 0.93),
    "LEFT_FOOT_INDEX": (0.44, 0.96),
    "RIGHT_FOOT_INDEX": (0.56, 0.96),
}

# (point_a, vertex, point_c, rotation_sign, segment_length)
_LIMB_GEOMETRY = {
    "elbow_flexion": ("LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST", 1.0, 0.16),
    "shoulder_flexion": ("LEFT_HIP", "LEFT_SHOULDER", "LEFT_ELBOW", -1.0, 0.16),
    "shoulder_abduction": ("LEFT_HIP", "LEFT_SHOULDER", "LEFT_ELBOW", -1.0, 0.16),
    "knee_flexion": ("LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE", 1.0, 0.17),
}


def _rotate_toward(a, b, angle_deg, length, sign):
    """Return point c such that angle(a, b, c) == angle_deg."""
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    direction = a - b
    direction = direction / (np.linalg.norm(direction) + 1e-9)
    phi = np.radians(angle_deg) * sign
    rotated = np.array([
        direction[0] * np.cos(phi) - direction[1] * np.sin(phi),
        direction[0] * np.sin(phi) + direction[1] * np.cos(phi),
    ])
    return b + rotated * length


def _build_pose(exercise_id: str, angle_deg: float) -> dict:
    """Build a full left-oriented normalized landmark dict for the given angle."""
    pose = {name: {"x": x, "y": y, "z": 0.0, "visibility": 0.99}
            for name, (x, y) in BASE_LANDMARKS.items()}

    a_name, b_name, c_name, sign, length = _LIMB_GEOMETRY[exercise_id]
    a = (pose[a_name]["x"], pose[a_name]["y"])
    b = (pose[b_name]["x"], pose[b_name]["y"])
    c = _rotate_toward(a, b, angle_deg, length, sign)
    pose[c_name]["x"], pose[c_name]["y"] = float(c[0]), float(c[1])

    # Keep wrist/hand attached when the computed joint is the elbow (shoulder work).
    if c_name == "LEFT_ELBOW":
        forearm = np.array([c[0] - b[0], c[1] - b[1]])
        forearm = forearm / (np.linalg.norm(forearm) + 1e-9)
        wrist = np.array([c[0], c[1]]) + forearm * 0.16
        pose["LEFT_WRIST"]["x"], pose["LEFT_WRIST"]["y"] = float(wrist[0]), float(wrist[1])
        for finger, offset in (("LEFT_PINKY", 0.03), ("LEFT_INDEX", 0.04), ("LEFT_THUMB", 0.03)):
            pose[finger]["x"] = float(wrist[0] + forearm[0] * offset)
            pose[finger]["y"] = float(wrist[1] + forearm[1] * offset)

    return pose


def _mirror_to_right(pose: dict) -> dict:
    """Mirror a left-oriented pose to the right side, swapping LEFT_/RIGHT_ names."""
    mirrored = {}
    for name, point in pose.items():
        if name.startswith("LEFT_"):
            new_name = "RIGHT_" + name[len("LEFT_"):]
        elif name.startswith("RIGHT_"):
            new_name = "LEFT_" + name[len("RIGHT_"):]
        else:
            new_name = name
        mirrored[new_name] = {
            "x": 1.0 - point["x"],
            "y": point["y"],
            "z": point["z"],
            "visibility": point["visibility"],
        }
    return mirrored


def _to_pixels(pose: dict) -> dict:
    return {
        name: {
            "x": point["x"] * IMAGE_WIDTH,
            "y": point["y"] * IMAGE_HEIGHT,
            "z": point["z"],
            "visibility": point["visibility"],
        }
        for name, point in pose.items()
    }


def _desired_angle(flexed: float, extended: float, progress: float) -> float:
    """Oscillate between flexed and extended across the session duration."""
    wave = 0.5 - 0.5 * np.cos(2.0 * np.pi * REPETITIONS * progress)
    return float(flexed + (extended - flexed) * wave)


def _ensure_patient(patient_repo) -> None:
    if not patient_repo.patient_exists(PATIENT_ID):
        patient_repo.create_patient({
            "patient_id": PATIENT_ID,
            "name": "Demo Patient",
            "status": "ACTIVE",
            "notes": NOTES_TAG,
        })
        return
    existing = patient_repo.get_patient(PATIENT_ID) or {}
    notes = existing.get("notes") or ""
    if NOTES_TAG not in notes:
        patient_repo.update_patient(PATIENT_ID, {"notes": f"{notes} {NOTES_TAG}".strip()})


def seed(exercise_id: str, side: str) -> str:
    exercise_def = get_exercise_definition(exercise_id, side=side)
    patient_repo = get_patient_repo()
    telemetry_repo = get_telemetry_repo()
    _ensure_patient(patient_repo)

    service = SessionService(
        session_repo=get_session_repo(),
        telemetry_repo=telemetry_repo,
        result_repo=get_result_repo(),
        patient_repo=patient_repo,
        assignment_repo=None,
    )

    start = service.start_session(
        StartSessionRequest(patient_id=PATIENT_ID, exercise=exercise_id, side=side)
    )
    session_id = start.session_id

    frame_count = int(DURATION_S * FPS)
    frame_interval_ms = int(1000 / FPS)
    base_time = utc_now()
    angles = []

    for i in range(frame_count):
        progress = i / float(frame_count)
        angle = _desired_angle(exercise_def.flexed_threshold, exercise_def.extended_threshold, progress)

        normalized = _build_pose(exercise_id, angle)
        if side == "right":
            normalized = _mirror_to_right(normalized)
        pixel_landmarks = _to_pixels(normalized)

        measured = calculate_angle(
            pixel_landmarks[exercise_def.landmarks[0]],
            pixel_landmarks[exercise_def.landmarks[1]],
            pixel_landmarks[exercise_def.landmarks[2]],
        )
        angles.append(measured)

        if measured <= exercise_def.flexed_threshold:
            phase = "FLEXED"
        elif measured >= exercise_def.extended_threshold:
            phase = "EXTENDED"
        else:
            phase = "MOVING"

        telemetry_repo.record_frame(
            session_id=session_id,
            frame_id=i + 1,
            landmarks=pixel_landmarks,
            joint_angles={exercise_def.joint_angle: round(float(measured), 3)},
            phase=phase,
            timestamp=base_time + timedelta(milliseconds=frame_interval_ms * i),
            image_width=IMAGE_WIDTH,
            image_height=IMAGE_HEIGHT,
        )

    rom_min = float(min(angles))
    rom_max = float(max(angles))
    rom_average = (rom_min + rom_max) / 2.0
    rom_excursion = rom_max - rom_min
    performance_score = min(100.0, max(0.0, (rom_excursion / exercise_def.target_rom) * 100.0))

    service.record_result(
        session_id,
        RecordResultRequest(
            repetitions=REPETITIONS,
            rom_min=round(rom_min, 2),
            rom_max=round(rom_max, 2),
            rom_average=round(rom_average, 2),
            performance_score=round(performance_score, 2),
            feedback=f"{NOTES_TAG}: {REPETITIONS} synthetic reps for {exercise_id} ({side}).",
        ),
    )
    service.end_session(session_id)
    return session_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a synthetic RehabTwin demo session.")
    parser.add_argument(
        "--exercise",
        choices=["elbow_flexion", "shoulder_flexion", "shoulder_abduction", "knee_flexion"],
        default="elbow_flexion",
    )
    parser.add_argument("--side", choices=["left", "right"], default="left")
    args = parser.parse_args()

    session_id = seed(args.exercise, args.side)
    print(session_id)


if __name__ == "__main__":
    main()
