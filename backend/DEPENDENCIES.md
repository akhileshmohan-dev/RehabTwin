# RehabTwin Backend Dependencies

This document describes the Python package requirements for running and developing the RehabTwin FastAPI backend API layer.

> [!NOTE]
> Per architectural constraints, the main repository `requirements.txt` file is **not modified**. All backend dependency specifications are documented here.

---

## Core Production Dependencies

These dependencies are required to run the FastAPI backend server:

| Package | Minimum Version | Purpose |
| :--- | :--- | :--- |
| `fastapi` | `>=0.100.0` | High-performance Web/REST framework & OpenAPI generation |
| `uvicorn` | `>=0.22.0` | ASGI web server implementation |
| `pydantic` | `>=2.0.0` | Request/response data validation and serialization |
| `sqlalchemy` | `>=2.0.0` | Database ORM engine used by `digital_thread` persistence |
| `opencv-python` | `>=4.8.0` | Media & image processing engine used by core pose estimation |
| `mediapipe` | `>=0.10.0` | Core pose landmark detector engine |

---

## Installation Commands

To install all required backend packages in your Python virtual environment:

```bash
pip install fastapi uvicorn pydantic sqlalchemy opencv-python mediapipe
```

---

## Optional Test & Development Dependencies

For enhanced automated testing with HTTP client integration:

| Package | Purpose |
| :--- | :--- |
| `httpx` | Required for `fastapi.testclient.TestClient` HTTP endpoint integration testing |
| `pytest` | Test runner alternative to standard library `unittest` |

Installation command for testing dependencies:

```bash
pip install httpx pytest
```
