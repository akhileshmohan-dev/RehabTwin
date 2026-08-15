# RehabTwin — Pose Estimation & Motion Acquisition

This module captures webcam video, detects body pose landmarks using MediaPipe,
and calculates joint angles (elbow, shoulder — both sides) in real time.

## Setup
1. Create venv: `py -3.12 -m venv venv`
2. Activate: `venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`

## Files
- `webcam_test.py` — basic webcam capture test
- `pose_test.py` — main script: runs pose detection + displays joint angles live
- `landmark_extractor.py` — converts MediaPipe output into structured landmark dict
- `angle_utils.py` — calculates joint angle from 3 landmark points

## Run
python pose_test.py

## Output format
extract_landmarks() returns a dict like:
{
  "LEFT_SHOULDER": {"x": ..., "y": ..., "z": ..., "visibility": ...},
  ...
}

calculate_angle(a, b, c) returns the angle in degrees at point b.