"""
FastAPI router handling exercise definitions, pose frame analysis, and real-time WebSocket skeleton.
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from backend.services.rehab_service import RehabService
from backend.schemas.analysis import (
    ExerciseListResponse,
    ExerciseInfo,
    ProcessFrameRequest,
    AnalysisResultResponse,
)

router = APIRouter(
    prefix="/api/analysis",
    tags=["Analysis"]
)


def get_rehab_service() -> RehabService:
    return RehabService()


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
    service: RehabService = Depends(get_rehab_service)
) -> AnalysisResultResponse:
    return service.process_pose_frame(request)


import base64
import numpy as np
import cv2
import mediapipe as mp

from pose_estimation.landmark_extractor import extract_landmarks
from pose_estimation.angle_utils import calculate_angle
from pose_estimation.pose_output import create_pose_frame
from rehabilitation.analysis_pipeline import ElbowAnalysisPipeline

@router.websocket("/ws/{session_id}")
async def real_time_telemetry_skeleton(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time live pose analysis stream.
    Receives base64 encoded JPEG images, processes them with MediaPipe,
    calculates clinical metrics using ElbowAnalysisPipeline, and returns
    the stateful results in real-time.
    """
    await websocket.accept()

    # 1. Create ONE ElbowAnalysisPipeline instance for that WebSocket connection
    pipeline = ElbowAnalysisPipeline(
        smoothing_window=5,
        flexed_threshold=100,
        extended_threshold=160
    )

    # 2. Create ONE MediaPipe Pose instance for that WebSocket connection
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose()

    try:
        while True:
            # 3. Receive base64 encoded JPEG image frames as text
            data = await websocket.receive_text()

            try:
                # Support either 'data:image/jpeg;base64,<payload>' or plain base64
                if "," in data:
                    b64_data = data.split(",")[1]
                else:
                    b64_data = data

                # 4. Decode each incoming image safely
                img_data = base64.b64decode(b64_data)
                np_arr = np.frombuffer(img_data, np.uint8)
                frame_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if frame_bgr is None:
                    raise ValueError("Failed to decode image array into an OpenCV frame.")
            except Exception as e:
                # 5. If image decoding fails: return JSON error message
                await websocket.send_json({
                    "type": "ANALYSIS_ERROR",
                    "message": f"Invalid image frame: {str(e)}"
                })
                continue

            # 6. Convert the decoded OpenCV BGR image into RGB
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            frame_height, frame_width = frame_rgb.shape[:2]

            # 7. Run MediaPipe pose processing
            results = pose.process(frame_rgb)

            # 8. If no pose landmarks are detected
            if not results.pose_landmarks:
                await websocket.send_json({
                    "type": "NO_POSE",
                    "session_id": session_id,
                    "message": "No pose detected"
                })
                continue

            # 9. When pose landmarks exist
            landmarks = extract_landmarks(results, frame_width, frame_height)

            if landmarks and "LEFT_SHOULDER" in landmarks and "LEFT_ELBOW" in landmarks and "LEFT_WRIST" in landmarks:
                calculated_angle = calculate_angle(
                    landmarks["LEFT_SHOULDER"],
                    landmarks["LEFT_ELBOW"],
                    landmarks["LEFT_WRIST"]
                )
                angles = {"left_elbow": calculated_angle}
                pose_frame = create_pose_frame(landmarks, angles)

                # 10. Pass that PoseFrame into the SAME persistent ElbowAnalysisPipeline instance
                analysis_dict = pipeline.process(pose_frame)

                # 11. Send analysis back over the WebSocket as JSON
                await websocket.send_json({
                    "type": "ANALYSIS_RESULT",
                    "session_id": session_id,
                    "raw_angle": analysis_dict.get("raw_angle"),
                    "valid_angle": analysis_dict.get("valid_angle"),
                    "smoothed_angle": analysis_dict.get("smoothed_angle"),
                    "state": analysis_dict.get("state"),
                    "repetitions": analysis_dict.get("repetitions"),
                    "rom": analysis_dict.get("rom", {})
                })
            else:
                await websocket.send_json({
                    "type": "NO_POSE",
                    "session_id": session_id,
                    "message": "Essential elbow landmarks not visible"
                })

    except WebSocketDisconnect:
        # 13. Handle WebSocketDisconnect cleanly
        pass
    except Exception as e:
        # 18. Add defensive exception handling
        try:
            await websocket.send_json({
                "type": "ANALYSIS_ERROR",
                "message": f"Server processing error: {str(e)}"
            })
        except:
            pass
    finally:
        # 14. MediaPipe cleanup must happen in a finally block
        pose.close()
