"""
FastAPI router handling exercise definitions, pose frame analysis, and real-time WebSocket.
"""
import base64
import json
import numpy as np
import cv2
import mediapipe as mp

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from backend.core.dependencies import get_session_repo, get_telemetry_repo, get_result_repo
from backend.repositories.interfaces import (
    ISessionRepository,
    ITelemetryRepository,
    IResultRepository,
)
from backend.services.rehab_service import RehabService
from backend.schemas.analysis import (
    ExerciseListResponse,
    ExerciseInfo,
    ProcessFrameRequest,
    AnalysisResultResponse,
)

from pose_estimation.landmark_extractor import extract_landmarks
from pose_estimation.angle_utils import calculate_angle
from pose_estimation.pose_output import create_pose_frame
from rehabilitation.analysis_pipeline import GenericAnalysisPipeline, ElbowAnalysisPipeline
from rehabilitation.exercises import ExerciseDefinition, get_exercise_definition
from rehabilitation.pose_validator import validate_pose, PoseStatusCode

router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"]
)


def get_rehab_service() -> RehabService:
    return RehabService()


# ---------------------------------------------------------------------------
# REST endpoints (unchanged)
# ---------------------------------------------------------------------------

@router.get(
    "/exercises",
    response_model=ExerciseListResponse,
    summary="List available exercise definitions"
)
def list_exercises(
    service: RehabService = Depends(get_rehab_service)
) -> ExerciseListResponse:
    return service.list_exercises()


@router.get(
    "/exercises/{exercise_id}",
    response_model=ExerciseInfo,
    summary="Get exercise details by ID"
)
def get_exercise(
    exercise_id: str,
    service: RehabService = Depends(get_rehab_service)
) -> ExerciseInfo:
    try:
        return service.get_exercise_details(exercise_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercise '{exercise_id}' not found."
        )


@router.post(
    "/process-frame",
    response_model=AnalysisResultResponse,
    summary="Process a single PoseFrame through rehabilitation analysis pipeline"
)
def process_frame(
    request: ProcessFrameRequest,
    service: RehabService = Depends(get_rehab_service),
    session_repo: ISessionRepository = Depends(get_session_repo),
) -> AnalysisResultResponse:
    if request.session_id:
        try:
            session_data = session_repo.get_session(request.session_id)
            session_side = (session_data.get("side") or "left").strip().lower()
            req_side = (request.side or "left").strip().lower()
            if req_side != session_side:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Requested side '{request.side}' does not match session side '{session_side}'",
                )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{request.session_id}' not found.",
            )
    try:
        return service.process_pose_frame(request)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown or unsupported exercise: '{request.exercise_id}'",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Performance score helper
# ---------------------------------------------------------------------------

def _compute_performance_score(rom_excursion: float | None, target_rom: float = 130.0) -> float:
    """Compute performance score from ROM excursion using exercise_def.target_rom."""
    if rom_excursion is None or target_rom <= 0.0:
        return 0.0
    return min(100.0, max(0.0, (rom_excursion / target_rom) * 100.0))


# ---------------------------------------------------------------------------
# Final result persistence helper
# ---------------------------------------------------------------------------

def _persist_final_result(
    session_id: str,
    pipeline: GenericAnalysisPipeline,
    result_repo: IResultRepository,
    exercise_def: ExerciseDefinition,
) -> dict:
    """
    Reads final state from pipeline, computes performance score using exercise_def.target_rom,
    persists through IResultRepository (idempotent), returns the payload dict.
    Does NOT mark the session COMPLETED.
    """
    state = pipeline.get_current_state()
    rom = state.get("rom") or {}
    rom_min = rom.get("min_angle")
    rom_max = rom.get("max_angle")
    rom_avg = (
        (rom_min + rom_max) / 2.0
        if rom_min is not None and rom_max is not None
        else None
    )
    rom_excursion = (
        (rom_max - rom_min)
        if rom_min is not None and rom_max is not None
        else None
    )
    repetitions = state.get("repetitions", 0)
    performance_score = _compute_performance_score(rom_excursion, exercise_def.target_rom)

    feedback_parts = []
    if repetitions > 0:
        feedback_parts.append(f"{repetitions} repetition(s) completed.")
    if rom_avg is not None:
        feedback_parts.append(f"Average ROM: {rom_avg:.1f} deg.")
    if performance_score >= 80:
        feedback_parts.append("Excellent range of motion.")
    elif performance_score >= 50:
        feedback_parts.append("Good effort. Keep improving.")
    else:
        feedback_parts.append("Continue working on your range of motion.")
    feedback = " ".join(feedback_parts)

    result_repo.record_result(
        session_id=session_id,
        repetitions=repetitions,
        rom_min=rom_min,
        rom_max=rom_max,
        rom_average=rom_avg,
        performance_score=performance_score,
        feedback=feedback,
    )

    return {
        "type": "FINAL_RESULT",
        "session_id": session_id,
        "repetitions": repetitions,
        "rom_min": rom_min,
        "rom_max": rom_max,
        "rom_average": rom_avg,
        "performance_score": performance_score,
        "feedback": feedback,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/{session_id}")
async def real_time_telemetry_skeleton(
    websocket: WebSocket,
    session_id: str,
    session_repo: ISessionRepository = Depends(get_session_repo),
    telemetry_repo: ITelemetryRepository = Depends(get_telemetry_repo),
    result_repo: IResultRepository = Depends(get_result_repo),
):
    """
    WebSocket endpoint for real-time live pose analysis stream.

    Protocol
    --------
    Client → Server:
        - Base64-encoded JPEG image (with or without data URI prefix)
        - JSON control: {"type": "END_SESSION"}

    Server → Client:
        - {"type": "ANALYSIS_RESULT", ...}
        - {"type": "NO_POSE", ...}
        - {"type": "ANALYSIS_ERROR", ...}
        - {"type": "FINAL_RESULT", ...}
        - {"type": "SESSION_REJECTED", ...}
    """
    await websocket.accept()

    # ------------------------------------------------------------------
    # 1. Session validation — must exist and be ACTIVE
    # ------------------------------------------------------------------
    try:
        session_data = session_repo.get_session(session_id)
    except KeyError:
        await websocket.send_json({
            "type": "SESSION_REJECTED",
            "session_id": session_id,
            "message": f"Session '{session_id}' does not exist.",
        })
        await websocket.close(code=4004)
        return

    if session_data.get("status") != "ACTIVE":
        await websocket.send_json({
            "type": "SESSION_REJECTED",
            "session_id": session_id,
            "message": (
                f"Session '{session_id}' is not ACTIVE "
                f"(current status: {session_data.get('status')})."
            ),
        })
        await websocket.close(code=4003)
        return

    exercise_id = session_data.get("exercise", "elbow_flexion")
    session_side = (session_data.get("side") or "left").strip().lower()
    try:
        exercise_def = get_exercise_definition(exercise_id, side=session_side)
    except KeyError:
        await websocket.send_json({
            "type": "SESSION_REJECTED",
            "session_id": session_id,
            "message": f"Unsupported exercise: '{exercise_id}'.",
        })
        await websocket.close(code=4004)
        return

    # ------------------------------------------------------------------
    # 2. Per-connection state — isolated, never global
    # ------------------------------------------------------------------
    pipeline = GenericAnalysisPipeline(exercise_def)

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose()

    # valid_frame_count counts only successfully processed valid frames.
    # No-pose frames never advance this counter.
    valid_frame_count: int = 0
    # frame_id increments for every persisted telemetry frame
    telemetry_frame_id: int = 0
    TELEMETRY_EVERY_N_VALID: int = 5  # persist ~2 FPS when streaming ~10 FPS

    try:
        while True:
            data = await websocket.receive_text()

            # ----------------------------------------------------------
            # 3. Detect JSON control messages first (e.g. END_SESSION)
            # ----------------------------------------------------------
            if data.strip().startswith("{"):
                try:
                    msg = json.loads(data)
                except json.JSONDecodeError:
                    msg = {}

                if msg.get("type") == "END_SESSION":
                    # Persist final result via IResultRepository (idempotent)
                    final_payload = _persist_final_result(
                        session_id, pipeline, result_repo, exercise_def
                    )
                    await websocket.send_json(final_payload)
                    # Do NOT mark session COMPLETED here.
                    # That is the REST endpoint's responsibility.
                    break  # Exit loop; client closes WebSocket then calls REST /end

                # Unknown control message — ignore gracefully
                continue

            # ----------------------------------------------------------
            # 4. Decode base64 JPEG image
            # ----------------------------------------------------------
            try:
                b64_data = data.split(",")[1] if "," in data else data
                img_bytes = base64.b64decode(b64_data)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame_bgr is None:
                    raise ValueError("OpenCV could not decode the image buffer.")
            except Exception as exc:
                await websocket.send_json({
                    "type": "ANALYSIS_ERROR",
                    "session_id": session_id,
                    "message": f"Invalid image frame: {exc}",
                })
                continue  # Bad frame — do not crash connection

            # ----------------------------------------------------------
            # 5. MediaPipe pose detection
            # ----------------------------------------------------------
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            frame_height, frame_width = frame_rgb.shape[:2]
            mp_results = pose.process(frame_rgb)

            landmarks = None
            if mp_results.pose_landmarks:
                landmarks = extract_landmarks(mp_results, frame_width, frame_height)

            # ----------------------------------------------------------
            # 6. Pose Validation (single source of truth)
            # ----------------------------------------------------------
            calculated_angle = None
            p_a, p_vertex, p_c = exercise_def.landmarks
            if landmarks and p_a in landmarks and p_vertex in landmarks and p_c in landmarks:
                try:
                    calculated_angle = calculate_angle(
                        landmarks[p_a],
                        landmarks[p_vertex],
                        landmarks[p_c],
                    )
                except Exception:
                    calculated_angle = None

            val_result = validate_pose(
                landmarks,
                exercise_def,
                calculated_angle=calculated_angle,
            )

            if not val_result.is_valid:
                # No-pose / Missing-landmarks condition: send structured NO_POSE
                if val_result.status in (
                    PoseStatusCode.NO_PERSON_DETECTED,
                    PoseStatusCode.REQUIRED_LANDMARKS_MISSING,
                ):
                    await websocket.send_json({
                        "type": "NO_POSE",
                        "session_id": session_id,
                        "status": val_result.status.value,
                        "message": val_result.message,
                        "missing_landmarks": val_result.missing_landmarks,
                        "low_visibility_landmarks": val_result.low_visibility_landmarks,
                    })
                else:
                    # Low-visibility or Invalid-angle condition:
                    # Send structured ANALYSIS_RESULT with valid_angle=None and pose_status
                    # Preserves client repetition/ROM state without advancing telemetry
                    current_state = pipeline.get_current_state()
                    await websocket.send_json({
                        "type": "ANALYSIS_RESULT",
                        "session_id": session_id,
                        "pose_status": val_result.to_dict(),
                        "raw_angle": val_result.raw_angle,
                        "valid_angle": None,
                        "smoothed_angle": None,
                        "state": current_state["state"],
                        "repetitions": current_state["repetitions"],
                        "rom": current_state["rom"],
                    })
                continue

            # ----------------------------------------------------------
            # 7. Valid Frame Pipeline analysis
            # ----------------------------------------------------------
            angles = {exercise_def.joint_angle: val_result.raw_angle}
            pose_frame = create_pose_frame(landmarks, angles)
            if pose_frame is not None:
                pose_frame["pose_validation"] = val_result.to_dict()

            analysis_dict = pipeline.process(pose_frame)

            # Only valid frames advance valid_frame_count and trigger telemetry
            valid_frame_count += 1

            # ----------------------------------------------------------
            # 8. Telemetry persistence - every 5th VALID frame (~2 FPS)
            #    Never stores JPEG bytes - only structured telemetry.
            # ----------------------------------------------------------
            if valid_frame_count % TELEMETRY_EVERY_N_VALID == 0 and pose_frame is not None:
                telemetry_frame_id += 1
                try:
                    telemetry_repo.record_frame(
                        session_id=session_id,
                        frame_id=telemetry_frame_id,
                        landmarks=pose_frame["landmarks"],
                        joint_angles=pose_frame["angles"],
                        phase=analysis_dict.get("state"),
                    )
                except Exception:
                    pass  # Telemetry write failure must never kill the live stream

            # ----------------------------------------------------------
            # 9. Send live analysis result to client
            # ----------------------------------------------------------
            await websocket.send_json({
                "type": "ANALYSIS_RESULT",
                "session_id": session_id,
                "pose_status": val_result.to_dict(),
                "raw_angle": analysis_dict.get("raw_angle"),
                "valid_angle": analysis_dict.get("valid_angle"),
                "smoothed_angle": analysis_dict.get("smoothed_angle"),
                "state": analysis_dict.get("state"),
                "repetitions": analysis_dict.get("repetitions"),
                "rom": analysis_dict.get("rom", {}),
            })

    except WebSocketDisconnect:
        # Unexpected disconnect — do NOT mark session COMPLETED.
        if valid_frame_count > 0:
            try:
                _persist_final_result(session_id, pipeline, result_repo, exercise_def)
            except Exception:
                pass  # Best-effort only; never raise on disconnect path

    except Exception as exc:
        # Unexpected server error — send error to client and exit cleanly
        try:
            await websocket.send_json({
                "type": "ANALYSIS_ERROR",
                "session_id": session_id,
                "message": f"Server processing error: {exc}",
            })
        except Exception:
            pass

    finally:
        # Always release MediaPipe resources
        pose.close()
