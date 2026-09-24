# RehabTwin — Pose Estimation & Motion Acquisition

This module captures webcam video, detects body pose landmarks using MediaPipe,
and calculates joint angles (elbow, shoulder — both sides) in real time.

## Setup
1. Create venv: `py -3.12 -m venv venv`
2. Activate: `venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`
   *(Note: This single command installs the dependencies required for both the pose-estimation components and the FastAPI backend)*

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

---

# Rehabilitation Analysis

The rehabilitation analysis module processes pose-estimation data and performs basic rehabilitation movement analysis.

It currently supports:

- Angle filtering
- Angle smoothing
- Elbow repetition counting
- Range of Motion (ROM) calculation
- CSV session logging

## Run

From the project root:

```powershell
python rehabilitation\live_analysis.py
````

### Webcam Setup

For the current elbow-flexion prototype:

1. Stand roughly sideways to the webcam.
2. Keep your shoulder, elbow, and wrist visible.
3. Start with your arm extended.
4. Slowly bend your elbow.
5. Slowly extend it again.
6. Repeat several times.
7. Press `q` to stop.

The live window displays:

```text
Elbow: <angle>
Reps: <count>
ROM: <range>
```

Session data is saved to:

```text
rehabilitation\elbow_motion.csv
```

The CSV is generated runtime data and is excluded from Git.

## Run Tests

From the project root:

```powershell
python -m pytest backend/tests/
```

The current test suite should show:

```text
34 passed
```

## Rehabilitation Pipeline

```text
Pose Estimation
      ↓
PoseFrame
      ↓
Angle Filtering
      ↓
Angle Smoothing
      ↓
Repetition Counting
      ↓
ROM Calculation
      ↓
Live Display + CSV
```

## Current Elbow Repetition Logic

A complete repetition is:

```text
EXTENDED → FLEXED → EXTENDED
```

Current prototype thresholds:

```text
Flexed:    100°
Extended:  160°
```

These thresholds are prototype parameters and are not clinically validated.

---

# Run locally (full stack)

Backend (FastAPI, port 8013):

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8013
```

Frontend (Vite + TanStack Start, port 8081):

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:8081` — therapist dashboard (`/therapist`), patient portal (`/patient`),
and the 3D replay dev page (`/replay-dev`).

Seed a synthetic completed session (structured telemetry only — no images/video are ever written):

```powershell
python scripts/seed_demo_session.py --exercise elbow_flexion --side left
```

Environment variables:

- `ALLOWED_ORIGINS` (backend) — comma-separated CORS origins. Defaults include `localhost`/`127.0.0.1`
  on ports 3000, 5173, 8080 and 8081; set this to override for other deployments.
- `TELEMETRY_EVERY_N_VALID` (backend) — persist every Nth valid pose frame; default `1` (every frame).
- `EXERCISE_CATALOG_PATH` (backend) — path to the exercise CSV; default `exercises/exercises.csv`.
- `VITE_API_BASE_URL` (frontend) — backend base URL. For local development this is set in
  `frontend/.env.local` to `http://127.0.0.1:8013` (WebSocket URLs derive from it automatically).

