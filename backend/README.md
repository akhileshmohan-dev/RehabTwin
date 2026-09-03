# RehabTwin FastAPI Backend API Layer

Production-grade integration and API layer for the **RehabTwin** computer-vision rehabilitation monitoring platform.

The backend acts as a clean, decoupled adapter layer exposing RESTful HTTP endpoints and WebSocket scaffolding over RehabTwin's core domain modules (`digital_thread`, `rehabilitation`, `pose_estimation`).

---

## 1. Architecture Overview

```
React Frontend
      │
      ▼ (HTTP / WebSocket)
FastAPI Backend (backend/main.py)
      │
      ▼
Routes / Controllers (backend/routes/)
      │
      ▼
Services Layer (backend/services/)
      │
   ┌──┴─────────────────────────┬──────────────────────────┐
   ▼                            ▼                          ▼
digital_thread             rehabilitation            pose_estimation
(Persistence Engine)    (Analysis & Exercises)    (Landmarks & Angles)
   │
   ▼
Database (SQLite / Postgres)
```

---

## 2. Directory Structure

```
backend/
├── main.py                   # Application entrypoint, CORS, exception handlers
├── DEPENDENCIES.md           # Dependency requirements and installation guide
├── README.md                 # Backend documentation and usage guide
│
├── core/
│   ├── __init__.py
│   └── dependencies.py       # FastAPI dependency injection getters & test overrides
│
├── routes/
│   ├── __init__.py
│   ├── sessions.py           # Session management & telemetry endpoints
│   ├── patients.py           # Patient history & listing endpoints
│   └── analysis.py           # Exercise catalog & frame processing endpoints
│
├── services/
│   ├── __init__.py
│   ├── session_service.py    # Wraps DigitalThread session lifecycle
│   ├── patient_service.py    # Wraps DigitalThread history & patient indexing
│   └── rehab_service.py      # Consumes rehabilitation analysis algorithms
│
├── schemas/
│   ├── __init__.py
│   ├── session.py            # Pydantic request/response models for sessions
│   ├── patient.py            # Pydantic request/response models for patients
│   └── analysis.py           # Pydantic request/response models for exercise/analysis
│
└── tests/
    ├── __init__.py
    └── test_api.py           # Unit tests covering endpoints, services, & 404 handling
```

---

## 3. How to Start the Server

From the root project directory, run:

```bash
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Once running:
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check**: `GET http://127.0.0.1:8000/health`

---

## 4. API Endpoints Reference

### Health Endpoints
- `GET /` - Discovery & status
- `GET /health` - Health check status

### Session Management (`/api/sessions`)
- `POST /api/sessions` - Start a new session
  - **Body**: `{"patient_id": "PATIENT-001", "exercise": "elbow_flexion"}`
- `GET /api/sessions/{session_id}` - Retrieve details of an existing session
- `POST /api/sessions/{session_id}/end` - Complete and close an active session
- `POST /api/sessions/{session_id}/frames` - Record pose landmark & joint angle frame telemetry
- `POST /api/sessions/{session_id}/results` - Record final performance metrics (reps, ROM, score, feedback)
- `GET /api/sessions/{session_id}/export` - Export session frames & results to JSON file

### Patient Management (`/api/patients`)
- `GET /api/patients` - List registered patients and total session counts
- `GET /api/patients/{patient_id}/sessions` - Retrieve complete session and result history for a patient

### Rehabilitation & Analysis (`/api/analysis`)
- `GET /api/analysis/exercises` - List available exercise definitions (e.g. `elbow_flexion`, `shoulder_flexion`)
- `GET /api/analysis/exercises/{exercise_id}` - Get metadata for a specific exercise
- `POST /api/analysis/process-frame` - Process a single `PoseFrame` through `ElbowAnalysisPipeline` (calculates raw/smoothed angles, state transitions, repetitions, and ROM)
- `WS /api/analysis/ws/{session_id}` - WebSocket skeleton endpoint for real-time telemetry streaming

---

## 5. Communication with Core Modules

- **`digital_thread/` Integration**: `SessionService` and `PatientService` instantiate and consume `DigitalThread`. All session lifecycle records, frame logs, result entries, and patient history queries route through `DigitalThread.start_session()`, `record_frame()`, `record_result()`, `end_session()`, `history()`, and `export_session()`.
- **`rehabilitation/` Integration**: `RehabService` imports exercise definitions from `rehabilitation.exercises` (`EXERCISES`, `get_exercise`) and executes frame analysis via `rehabilitation.analysis_pipeline.ElbowAnalysisPipeline` without modifying or duplicating algorithm code.
- **`pose_estimation/` Integration**: Consumed by frame creation and processing utilities (`create_pose_frame`, `calculate_angle`, `extract_landmarks`).

---

## 6. How the Frontend Communicates with the API

The React frontend (`frontend/`) makes standard asynchronous HTTP requests (using `fetch` or `axios`) to `http://localhost:8000/api/...`.

- CORS middleware is pre-configured on the backend to allow local frontend cross-origin requests.
- All request payloads and response bodies adhere strictly to Pydantic JSON schemas.

---

## 7. Running Backend Unit Tests

To run the automated backend unit test suite:

```bash
python -m unittest discover -s backend/tests
```

All tests execute in isolated, in-memory databases and mock webcam streams, ensuring fast and reliable execution without physical camera dependencies.

---

## 8. Real-time Live Analysis & Future Work

- **Current State**: Live webcam capture and real-time visualization are currently handled locally by `rehabilitation/live_analysis.py`.
- **WebSocket Skeleton**: The endpoint `WS /api/analysis/ws/{session_id}` in `backend/routes/analysis.py` provides the structural scaffolding for streaming video frame landmarks from a Web browser client.
- **Future Integration**: Future work involves creating a browser-compatible pose detector client (using MediaPipe JS) that streams landmarks directly over WebSockets to `WS /api/analysis/ws/{session_id}` for server-side pipeline evaluation.
