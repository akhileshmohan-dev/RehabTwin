# RehabTwin — Pose Estimation, Rehabilitation Analysis & Digital Thread

RehabTwin captures webcam pose data with MediaPipe, calculates joint angles, performs rehabilitation analysis, and now records each rehabilitation session as a persistent **Digital Thread**.

## Pipeline

```text
Camera
  ↓
MediaPipe Pose
  ↓
Landmarks
  ↓
Joint Angles
  ↓
Filtering + Smoothing
  ↓
Repetition Counting + ROM
  ↓
Digital Thread
  ├── Session
  ├── Frame landmarks
  ├── Joint-angle measurements
  └── Session result
  ↓
SQLite (now) → PostgreSQL (later)
```

## Setup

```powershell
py -3.12 -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The project uses **SQLAlchemy** as the persistence abstraction. SQLite is the default local database. PostgreSQL is intentionally not required yet.

## Run live rehabilitation analysis

From the project root:

```powershell
python rehabilitation\live_analysis.py --patient-id P001
```

The program will:

1. Start a Digital Thread session.
2. Run the existing MediaPipe + elbow-analysis pipeline.
3. Persist each analyzed frame's landmarks, angle data, and movement state.
4. Save the final repetition and ROM result.
5. Export a complete session JSON trace.

Default outputs:

```text
data\rehabtwin_thread.db

data\exports\<SESSION_ID>.json

rehabilitation\elbow_motion.csv
```

The live window displays:

```text
Elbow: <angle>
Reps: <count>
ROM: <range>
```

## Digital Thread API

The rehabilitation pipeline only talks to this interface:

```python
from digital_thread import DigitalThread

thread = DigitalThread()
session_id = thread.start_session("P001", "elbow_flexion")

thread.record_frame(
    frame_id=0,
    landmarks={...},
    joint_angles={
        "left_elbow_raw": 151.2,
        "left_elbow_smoothed": 149.8,
    },
    phase="EXTENDED",
)

thread.record_result(
    repetitions=12,
    rom_min=48.0,
    rom_max=142.0,
    rom_average=94.0,
    performance_score=None,
    feedback="Session recorded successfully.",
)

thread.end_session()
```

This keeps the pose/analysis code database-agnostic.

## Database structure

```text
sessions
    │
    ├── frames
    │
    └── results
```

Each frame belongs to exactly one session, and each result belongs to exactly one session.

## PostgreSQL migration path

SQLite is the local default. Later, PostgreSQL can be selected through `DATABASE_URL` without changing the Digital Thread API:

```powershell
$env:DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/rehabtwin"
python rehabilitation\live_analysis.py --patient-id P001
```

Install the PostgreSQL driver when the migration phase begins:

```powershell
pip install "psycopg[binary]>=3.2,<4"
```

To migrate an existing SQLite database:

```powershell
python scripts\migrate_sqlite_to_target.py `
  --source data\rehabtwin_thread.db `
  --target "postgresql+psycopg://USER:PASSWORD@HOST:5432/rehabtwin"
```

The migration script creates the target schema from the same SQLAlchemy models and copies sessions, frames, and results.

## Existing pose-estimation modules

- `pose_estimation/webcam_test.py` — webcam capture test
- `pose_estimation/pose_test.py` — pose detection and display
- `pose_estimation/landmark_extractor.py` — structured landmarks
- `pose_estimation/angle_utils.py` — joint-angle calculation

## Rehabilitation modules

- `rehabilitation/data_filter.py` — visibility/validity filtering
- `rehabilitation/smoothing.py` — angle smoothing
- `rehabilitation/repetition_counter.py` — elbow repetition state machine
- `rehabilitation/rom_calculator.py` — ROM calculation
- `rehabilitation/analysis_pipeline.py` — analysis orchestration
- `rehabilitation/live_analysis.py` — webcam session + Digital Thread integration

## Tests

Run the non-hardware test suite from the project root:

```powershell
python -m pytest tests/test_analysis_pipeline.py tests/test_data_filter.py tests/test_exercises.py tests/test_repetition_counter.py tests/test_rom_calculator.py tests/test_smoothing.py tests/test_digital_thread.py -v
```

Webcam-dependent test scripts are intentionally not included in the headless test command.

## Current elbow logic

A complete repetition is:

```text
EXTENDED → FLEXED → EXTENDED
```

Prototype thresholds:

```text
Flexed:    100°
Extended:  160°
```

These thresholds are prototype parameters and are not clinically validated.
