# RehabTwin

## Human Digital Twin for Rehabilitation

RehabTwin is a modular rehabilitation system combining webcam-based human pose estimation, Unity avatar tracking, patient and session management, historical session replay, exercise configuration, rehabilitation analysis, a Digital Thread for storing session history, and comparison of measured results against therapist-defined targets.

The architecture is split into capture, visualization, analysis, storage, and comparison layers. The frontend should use stable application concepts and service/module interfaces rather than depend directly on MediaPipe internals, Unity GameObjects, Mixamo bone names, SQLite tables, or developer-specific filesystem paths.

**Current working branch:** 3d-model-twin-thread

**Current status:** Core live/replay, patient management, exercise analysis, Digital Thread integration, and target comparison are implemented and tested. Production HTTP/API wrapping and final standalone deployment packaging are still to be finalized.

---

# 1. High-Level Architecture

    FRONTEND
       |
       v
    RehabTwin module interfaces
       |
       +---- Patient Manager
       +---- Session Controller
       +---- Exercise Manager
                 |
          +------+------+
          |             |
          v             v
        LIVE          REPLAY
          |             |
          v             v
      MediaPipe     Session JSON
          |             |
          +------+------+
                 |
                 v
              PoseFrame
                 |
          +------+------+
          |             |
          v             v
    Unity Avatar    Session Analyzer
                         |
                         v
                   Digital Thread
                         |
                         v
                   Exercise Approver
                         |
                         v
                   Combined Result

Key design decision: LIVE and REPLAY converge on the same PoseFrame representation.

---

# 2. Technology Stack

## Python

The Python side handles pose processing, rehabilitation analysis, exercise configuration, Digital Thread integration, and result comparison.

Current development environment:

- Python 3.12.10
- MediaPipe 0.10.21
- OpenCV / OpenCV-Contrib
- NumPy 1.26.4
- SQLAlchemy
- Matplotlib
- PyTest
- Sounddevice

The existing development environment is the .venv directory. Do not commit it.

## Unity

Unity currently provides:

- 3D avatar representation
- Live pose visualization
- Replay visualization
- Session orchestration
- Patient selection during development
- Communication with the Python live-pose process

The final target is a standalone Windows Unity build; the foreign machine should not require the Unity Editor.

## Communication

During development, the Python live-pose process sends local UDP data to:

    127.0.0.1:5005

This is an internal transport. The frontend should not need to implement or depend on it.

---

# 3. Core Pose Pipeline

    Webcam
      ↓
    MediaPipe Pose
      ↓
    33 landmarks
      ↓
    Pose validation
      ↓
    Pose processing
      ↓
    PoseFrame
      ├──→ Unity Avatar Tracking
      ├──→ Session Recording
      └──→ Exercise Analysis

---

# 4. Pose Data Model

## PoseLandmark

Each landmark contains:

    name
    x
    y
    z
    visibility
    world_x
    world_y
    world_z

## PoseFrame

Unity uses:

    PoseFrame
    └── PoseLandmark[] landmarks

PoseFrame also supports name-based landmark lookup so downstream modules do not have to depend on array indexes.

The live Python payload is wrapped as an object containing a landmarks array with all 33 pose landmarks.

---

# 5. Pose Validation

Current validation behavior includes:

- Expected landmark count: 33
- Minimum visibility: 0.5
- Multiple valid/stable frames are required before tracking is ready
- Invalid-frame tolerance exists before a pose is considered lost

Validator states:

    WAITING
    READY
    TRACKING
    HOLDING
    LOST

Normal movement during setup is not treated as invalid simply because the person moved. Validation focuses on pose quality and landmark availability.

---

# 6. Calibration

Unity pose calibration establishes a reference before avatar tracking begins.

Current calibration settings:

    Stable frames: 15
    Visibility threshold: 0.5
    Stability threshold: 0.015

Reference values include:

- Hip center
- Shoulder center
- Shoulder width
- Torso length

Calibration can be reset when a session ends.

---

# 7. Unity Avatar Tracking

The active avatar tracker maps pose landmarks onto a Mixamo-style humanoid.

Current mapped regions:

    Torso:
      Hips
      Spine
      Spine1
      Spine2

    Left arm:
      Shoulder
      Upper Arm
      Forearm
      Hand

    Right arm:
      Shoulder
      Upper Arm
      Forearm
      Hand

    Left leg:
      Upper Leg
      Lower Leg
      Foot

    Right leg:
      Upper Leg
      Lower Leg
      Foot

Tracking uses landmark-to-landmark direction vectors and applies rotations relative to the avatar rest pose.

The tracker also provides:

- Tracking enable/disable
- Rotation smoothing
- Visibility filtering
- Short-term landmark holding
- Reset to rest pose

## MediaPipe 3D limitation

MediaPipe is camera-based rather than a direct 3D motion-capture system.

Therefore:

- Depth is estimated rather than directly measured
- Occlusion can reduce landmark reliability
- Camera angle and body orientation can affect estimated depth
- Physically accurate 3D reconstruction is not guaranteed

The current practical focus is reliable camera-plane movement with a 3D avatar visualization.

---

# 8. Unity Session Controller

The main Unity orchestrator is RehabTwinSessionController.

High-level session states:

    IDLE
    LIVE
    REPLAY

Responsibilities include:

- Active patient selection
- Start and stop live mode
- Start and stop replay
- Start and stop recording
- Python process lifecycle
- Avatar tracking enable/disable
- Session finalization
- Replay lifecycle

Keyboard-based recording control was intentionally removed so the Session Controller, and eventually the frontend, owns session state.

---

# 9. Live Session Flow

    Select Patient
          ↓
    Start Live
          ↓
    Start Python pose process
          ↓
    Enable avatar tracking
          ↓
    Start recording
          ↓
    MediaPipe captures pose
          ↓
    Valid pose data reaches Unity
          ↓
    Avatar follows movement
          ↓
    End Session
          ↓
    Session JSON saved

---

# 10. Session Recording

PoseSessionRecorder records valid Unity poses at approximately 30 FPS.

The session contains:

    sessionId
    createdAt
    duration
    frameCount
    frames[]

Each recorded frame contains:

    time
    pose

Only valid current poses are recorded.

The session recorder does not own overall application state; the Session Controller starts and stops it.

---

# 11. Patient Management

Patient functionality currently supports:

    List patients
    Create patient
    Select patient
    Check patient existence
    Check whether patient has sessions
    Get session count

Patient IDs are normalized to uppercase.

Allowed characters:

    A-Z
    a-z
    0-9
    _
    -

Examples:

    PATIENT_001
    PATIENT_002

---

# 12. Patient Storage

Current development structure:

    data/
    └── patients/
        ├── PATIENT_001/
        │   ├── profile.json
        │   └── sessions/
        │       └── Session_*.json
        └── PATIENT_002/
            ├── profile.json
            └── sessions/
                └── Session_*.json

A patient profile contains fields such as:

    patient_id
    name
    created_at
    updated_at

Patient-specific session isolation has been tested.

---

# 13. Replay

PoseSessionReplay loads a historical session and feeds stored poses back through the Unity pose path.

    Session JSON
       ↓
    Replay Controller
       ↓
    PoseFrame
       ↓
    Avatar Tracking

Supported operations include:

    Load session
    Start replay
    Pause replay
    Restart replay
    Read current frame
    Read replay time
    Read duration

This provides the foundation for historical therapist review and future session-to-session comparison.

---

# 14. Exercise Configuration

Exercise definitions are imported from:

    exercises/exercises.csv

The current CSV contains 40 exercise definitions.

Current columns include:

    sequence_id
    sequence_name
    exercise_id
    exercise_name
    target_joint
    side
    min_angle
    max_angle
    target_reps

The internal normalized exercise object contains:

    exercise_id
    exercise_name
    target_joint
    side
    rom_min_deg
    rom_max_deg
    target_reps
    extra

ROM aliases supported:

    rom_min_deg OR min_angle
    rom_max_deg OR max_angle

## Configuration ownership

RehabTwin imports and validates exercise configuration. It does not currently provide an exercise editing UI.

The therapist/frontend side can own:

- Exercise editing UI
- Therapist-entered thresholds
- Exercise sequence selection
- Target ROM
- Target repetitions

RehabTwin consumes the resulting configuration.

---

# 15. Exercise Analysis

The Unity-session analysis bridge is:

    rehabilitation/session_analyzer.py

It reads a completed Unity PoseSession JSON and produces exercise-specific metrics.

Current target joints include:

    elbow
    shoulder

Current side concepts include:

    left
    right
    both

## Elbow angle

Calculated from:

    Shoulder → Elbow → Wrist

## Shoulder angle

Calculated from:

    Hip → Shoulder → Elbow

## Smoothing

A moving-average filter is used with a default window size of 5 frames.

## Repetition counting

Current default elbow thresholds:

    Flexed:    100°
    Extended:  160°

The movement phase concept is:

    EXTENDED → FLEXED → EXTENDED

Exercise configuration can provide threshold overrides through optional fields.

## ROM

The analyzer records:

    rom_min
    rom_max
    rom_average

A verified development result included:

    Exercise: ELBOW_FLEX_01
    Recorded repetitions: 10
    Recorded ROM approximately: 7.17° → 179.42°

These are development/test results, not clinical benchmarks.

---

# 16. Digital Thread

The Digital Thread is the rehabilitation data backbone.

It is currently SQLite-backed, with SQLAlchemy used as the persistence abstraction.

Main entities:

## Session

    session_id
    patient_id
    exercise
    started_at
    ended_at
    status

## Frame

    session_id
    frame_id
    timestamp
    landmarks
    joint_angles
    phase

## Result

    session_id
    exercise
    repetitions
    rom_min
    rom_max
    rom_average
    performance_score
    feedback

The Digital Thread is a data backbone, not the motion-analysis algorithm itself.

## Digital Thread flow

    Unity PoseSession JSON
            ↓
    Session Analyzer
            ↓
    Digital Thread Session
            ↓
    Frame records
            ↓
    Exercise Result
            ↓
    JSON export

The Unity sessionId is reused as the Digital Thread session_id for traceability.

## Timestamp caveat

The current Digital Thread frame-recording path can generate its own timestamp instead of always preserving the original Unity frame timestamp. Exact source timeline preservation is a remaining productionization task.

---

# 17. Exercise Approver

The comparison module is:

    exercises/exercise_approver.py

It compares therapist-defined targets against the measured Digital Thread result.

Relevant fields include:

    patient_id
    session_id
    exercise_id
    exercise_name

    target ROM minimum
    target ROM maximum
    target repetitions

    recorded ROM minimum
    recorded ROM maximum
    recorded ROM average
    recorded repetitions

    ROM minimum error
    ROM maximum error
    target ROM span
    recorded ROM span
    ROM coverage percentage

    rom_range_reached
    reps_target_reached

The approver strictly matches the requested exercise by exercise_id or exercise_name and does not silently use an unrelated result.

The approver provides structured comparison data for frontend/therapist interpretation. It is not a replacement for clinical judgement.

---

# 18. Session Service

The high-level orchestration module is:

    rehabilitation/session_service.py

Main class:

    RehabTwinSessionService

Flow:

    Unity PoseSession
          ↓
    Session Analyzer
          ↓
    Digital Thread
          ↓
    Exercise Approver
          ↓
    Combined Result

Public Python operation:

    process_session(
        unity_session_path,
        exercise_id,
        exercise_csv_path="exercises/exercises.csv",
        database_url=None
    )

Returned data contains:

    session
    measured_result
    comparison
    digital_thread_export
    approval_export

Important integration status: this is currently a Python module/function interface, not an implemented HTTP REST API. A REST, WebSocket, or similar API layer can be placed above it later.

---

# 19. Frontend Integration Boundary

The frontend should work with these concepts:

    Patient
    Exercise
    Session
    Measured Result
    Comparison Result
    Replay State
    History

## Patient Manager

    List patients
    Create patient
    Select patient
    Read patient profile
    Check session availability
    Read session count

## Session Controller

    Start live
    Stop live
    Start replay
    Pause replay
    Stop replay
    Get current session state
    Get active patient

## Exercise Manager

    List exercises
    Get exercise by ID
    Read target joint
    Read side
    Read ROM limits
    Read target repetitions

## Analysis Service

    Process completed session
    Calculate metrics
    Store result
    Return repetitions
    Return ROM
    Return comparison
    Return export references

## Replay Engine

    Load session
    Start
    Pause
    Restart
    Get position
    Get duration

## Digital Thread

    Persist sessions
    Persist frame history
    Persist results
    Export history/results

The frontend should normally consume service output instead of accessing the database directly.

---

# 20. Important IDs

## Patient ID

Example:

    PATIENT_002

Used to isolate patient data.

## Exercise ID

Example:

    ELBOW_FLEX_01

Used to identify the configured exercise and match analysis results.

## Session ID

A unique ID for a recorded session.

It connects:

    Unity session
    Digital Thread session
    session export
    approval export

Frontend code should treat these as identifiers and not depend on their internal generation.

---

# 21. Frontend Result Contract

A processed session is conceptually shaped like:

    session
      session_id
      patient_id
      exercise_id
      exercise_name
      selected_side

    measured_result
      repetitions
      rom_min
      rom_max
      rom_average

    comparison
      target_reps
      recorded_reps
      target_rom_min
      target_rom_max
      recorded_rom_min
      recorded_rom_max
      rom_coverage_percent
      rom_range_reached
      reps_target_reached

    digital_thread_export
    approval_export

Exact numeric values depend on the recorded session.

---

# 22. Current Storage Layout

    RehabTwin(V4)/
    ├── data/
    │   ├── patients/
    │   │   └── <PATIENT_ID>/
    │   │       ├── profile.json
    │   │       └── sessions/
    │   │           └── Session_*.json
    │   └── exports/
    │       ├── <session_id>.json
    │       └── <session_id>_approval.json
    │
    ├── digital_thread/
    ├── exercises/
    │   ├── __init__.py
    │   ├── exercise_config.py
    │   ├── exercise_approver.py
    │   └── exercises.csv
    ├── pose_estimation/
    ├── rehabilitation/
    │   ├── session_analyzer.py
    │   ├── session_service.py
    │   └── supporting analysis modules
    ├── tests/
    ├── requirements.txt
    └── README.md

---

# 23. Important Python Modules

Most important for integration:

    rehabilitation/session_service.py
    rehabilitation/session_analyzer.py
    exercises/exercise_config.py
    exercises/exercise_approver.py
    digital_thread/

Supporting packages:

    pose_estimation/
    rehabilitation/
    digital_thread/

---

# 24. Important Unity Components

Active Unity architecture includes components such as:

    PoseLandmark
    PoseFrame
    BoneMap
    PoseCalibrator
    PoseReceiver
    AvatarTrackingController
    PoseSessionRecorder
    PoseSessionReplay
    RehabTwinSessionController
    PatientDirectory
    PatientSelectionController
    RehabTwinPathResolver

Older experimental movement-controller scripts are not part of the active tracking flow.

---

# 25. Development Setup

Use the existing Python 3.12 environment.

    cd "D:\RehabTwin_Vaisakh\RehabTwin(V4)"
    .\.venv\Scripts\Activate.ps1
    python --version
    python -m pip install -r requirements.txt

Expected development version:

    Python 3.12.10

Quick analyzer import test:

    python -c "from rehabilitation.session_analyzer import UnitySessionAnalyzer; print('Session Analyzer import: OK')"

Analyze a completed Unity session:

    python -m rehabilitation.session_analyzer <unity_session.json> <exercise_id> [exercise_csv]

Example:

    python -m rehabilitation.session_analyzer ^
      data/patients/PATIENT_002/sessions/Session_XXXX.json ^
      ELBOW_FLEX_01 ^
      exercises/exercises.csv

Digital Thread exports are written under:

    data/exports/

---

# 26. Deployment Plan

Current development layout:

    D:\RehabTwin_Vaisakh\
    ├── RehabTwin(V4)\
    └── RehabTwin_Unity\

The current path resolver supports this development relationship, but this is not the final foreign-machine deployment model.

Target deployment:

    Frontend
       ↓
    Standalone RehabTwin application
       ├── Unity runtime
       └── Standalone backend runtime

The target machine should not require:

    Unity Editor
    manual Python installation
    development virtual-environment setup
    developer-specific D: paths

The backend is expected eventually to be packaged as a standalone executable such as:

    RehabTwinBackend.exe

The final portable/installer layout, writable-data strategy and production path resolver are still to be finalized.

---

# 27. Testing Completed

Core development verification has covered:

- 33-landmark MediaPipe extraction
- Pose validation
- Pose calibration
- Unity avatar tracking
- Live session start/stop
- Session recording
- Patient creation and selection
- Patient-specific storage
- Patient-isolated replay
- Exercise CSV import
- Current 40 exercise definitions
- Unity Session to Session Analyzer bridge
- Digital Thread integration/export
- Exercise target comparison
- Combined session-service processing
- End-to-end record to analyze to approval flow

A real PATIENT_002 test flow successfully produced exercise-analysis output for ELBOW_FLEX_01, including a 10-repetition result and measured ROM around 7.17° to 179.42°.

These are development/test results, not clinical benchmarks.

---

# 28. Known Limitations

### Depth accuracy

Camera-based pose estimation does not guarantee physically accurate 3D depth.

### Occlusion

Hidden joints may produce unreliable landmarks.

### Camera setup

Lighting, distance, framing, background and viewpoint affect tracking quality.

### Clinical interpretation

The system produces movement metrics and comparisons. It does not replace therapist or clinician judgement.

### Timestamp fidelity

Source Unity timestamps should eventually be preserved exactly in the Digital Thread when precise timeline reconstruction matters.

### API layer

The current high-level service is a Python interface. Production HTTP/WebSocket endpoints are not yet implemented.

### Deployment

Standalone backend packaging, standalone Unity release, installer/distribution and production path handling remain to be finalized.

---

# 29. Version Control Rules

Do not commit generated or machine-specific content:

    .venv/
    __pycache__/
    .pytest_cache/
    .vscode/
    .idea/
    *.pyc
    *.log
    *.db
    *.sqlite
    *.sqlite3
    data/patients/*
    data/exports/*

Unity generated directories should also remain outside source control:

    Library/
    Temp/
    Logs/
    Obj/
    UserSettings/
    .vs/

Commit source code, configuration, project settings, required Unity assets, tests, and other files needed to recreate the application.

---

# 30. Frontend Development Rules

The frontend should not directly depend on:

    MediaPipe internals
    Unity GameObjects
    Mixamo bone names
    UDP implementation details
    SQLite tables
    Internal smoothing/repetition algorithms
    Developer-specific filesystem paths

Prefer stable concepts:

    patient_id
    exercise_id
    session_id
    session_state
    exercise configuration
    measured metrics
    comparison result
    replay position
    history/result records

Do not assume every exercise is an elbow exercise. Exercise behavior is configuration-driven through target_joint, side, ROM limits and target repetitions.

---

# 31. Proposed Future API Boundary

A future network/API layer can expose operations conceptually like:

    GET  /patients
    POST /patients
    GET  /patients/{patient_id}
    GET  /patients/{patient_id}/sessions

    GET  /exercises
    GET  /exercises/{exercise_id}

    POST /sessions/live/start
    POST /sessions/live/stop
    POST /sessions/{session_id}/analyze
    GET  /sessions/{session_id}/result
    GET  /sessions/{session_id}/comparison

    POST /replay/{session_id}/start
    POST /replay/{session_id}/pause
    POST /replay/{session_id}/restart

These are proposed interface boundaries only. They are not current HTTP endpoints.

---

# 32. Design Principles

### Modular

Each major layer can be replaced or upgraded independently.

### Data-driven

Exercise targets come from configuration rather than per-exercise hard-coded UI logic.

### Consistent pose representation

Live and replay both use PoseFrame.

### Patient isolation

Sessions are stored beneath patient-specific directories.

### Traceability

Session IDs connect Unity records, Digital Thread records, and exported results.

### Frontend independence

The UI should consume public service/module concepts rather than internal implementation details.

### Honest measurement boundaries

The system reports movement metrics without claiming camera-estimated depth is ground truth or that automated comparison replaces clinical judgement.

---

# 33. Recommended Frontend Workflow

    1. Load patients
    2. Select patient
    3. Load exercises
    4. Select exercise
    5. Start Live
    6. Display live camera/avatar experience
    7. End session
    8. Process session
    9. Display repetitions + ROM
    10. Display target comparison
    11. Show patient history
    12. Replay previous sessions when required

---

# 34. Final Quick Reference

    PATIENT
      ↓
    EXERCISE
      ↓
    SESSION
      ↓
    LIVE / REPLAY
      ↓
    POSEFRAME
      ↓
    ANALYSIS
      ↓
    DIGITAL THREAD
      ↓
    COMPARISON
      ↓
    RESULT

Most important IDs:

    patient_id
    exercise_id
    session_id

Most important exercise fields:

    exercise_id
    exercise_name
    target_joint
    side
    rom_min_deg
    rom_max_deg
    target_reps

Most important result fields:

    repetitions
    rom_min
    rom_max
    rom_average
    rom_coverage_percent
    rom_range_reached
    reps_target_reached

Most important backend modules:

    rehabilitation/session_service.py
    rehabilitation/session_analyzer.py
    exercises/exercise_config.py
    exercises/exercise_approver.py
    digital_thread/

---

# 35. Final Architecture Summary

    FRONTEND
        |
        v
    RehabTwin Interfaces
        |
        +-- Patient Manager
        +-- Session Controller
        +-- Exercise Manager
                     |
              +------+------+
              |             |
              v             v
            LIVE          REPLAY
              |             |
              v             v
          MediaPipe      Session JSON
              |             |
              +------+------+
                     |
                     v
                  PoseFrame
                     |
               +-----+-----+
               |           |
               v           v
         Unity Avatar   Session Analyzer
                            |
                            v
                      Digital Thread
                            |
                            v
                      Exercise Approver
                            |
                            v
                        Final Result

Core principle: capture movement once, represent it consistently, analyze it using configurable exercise definitions, preserve it in patient history, and expose structured results to the frontend.
