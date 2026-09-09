import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  CameraOff,
  Play,
  Square,
  AlertCircle,
  Loader2,
  CheckCircle2,
  RotateCcw,
} from "lucide-react";
import { startSession, endSession, getWebSocketUrl, fetchExercises } from "@/data/rehabService";
import type { Exercise } from "@/types/rehab";

export const Route = createFileRoute("/patient")({
  head: () => ({
    meta: [
      { title: "RehabTwin - Patient Portal" },
      {
        name: "description",
        content: "Patient portal for live rehabilitation exercises and camera tracking.",
      },
    ],
  }),
  component: PatientPortal,
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type CameraStatus = "idle" | "loading" | "active" | "error";
type SessionStatus = "idle" | "starting" | "active" | "error" | "ending" | "completed";

interface LiveStats {
  repetitions: number;
  rawAngle: number | null;
  smoothedAngle: number | null;
  state: string;
  romMin: number | null;
  romMax: number | null;
}

interface FinalResult {
  repetitions: number;
  romMin: number | null;
  romMax: number | null;
  romAverage: number | null;
  performanceScore: number;
  feedback: string;
}

export type PoseStatusCode =
  | "VALID"
  | "NO_PERSON_DETECTED"
  | "REQUIRED_LANDMARKS_MISSING"
  | "LOW_VISIBILITY"
  | "INVALID_ANGLE"
  | "ERROR";

export interface PoseFeedback {
  code: PoseStatusCode;
  message: string;
  missingLandmarks: string[];
  lowVisibilityLandmarks: string[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const FRAME_INTERVAL_MS = 100; // ~10 FPS target
const JPEG_QUALITY = 0.7;
const CANVAS_WIDTH = 320;
const CANVAS_HEIGHT = 240;
// Backpressure threshold: 64KB allows ~4-5 frames in flight (~10-15KB each)
// without dropping, but prevents unbounded accumulation during network/processing lag.
const MAX_BUFFERED_AMOUNT = 65536;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
function PatientPortal() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const endSessionResolveRef = useRef<(() => void) | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sessionStatusRef = useRef<SessionStatus>("idle");
  const pendingFinalResultRef = useRef<{ sessionId: string; result: FinalResult } | null>(null);

  const [stream, setStream] = useState<MediaStream | null>(null);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("idle");
  const [cameraError, setCameraError] = useState<string>("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Keep sessionStatusRef in sync for event listeners/closures
  useEffect(() => {
    sessionStatusRef.current = sessionStatus;
  }, [sessionStatus]);

  // Exercise catalog & selection state
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<Exercise | null>(null);
  const [selectedSide, setSelectedSide] = useState<"left" | "right">("left");
  const [activeSessionExercise, setActiveSessionExercise] = useState<Exercise | null>(null);
  const [activeSessionSide, setActiveSessionSide] = useState<"left" | "right">("left");
  const [exercisesLoading, setExercisesLoading] = useState(true);
  const [exercisesError, setExercisesError] = useState("");

  const [liveStats, setLiveStats] = useState<LiveStats>({
    repetitions: 0,
    rawAngle: null,
    smoothedAngle: null,
    state: "-",
    romMin: null,
    romMax: null,
  });
  const [poseStatus, setPoseStatus] = useState<"ok" | "missing" | "error">("ok");
  const [poseFeedback, setPoseFeedback] = useState<PoseFeedback>({
    code: "VALID",
    message: "Pose tracking active",
    missingLandmarks: [],
    lowVisibilityLandmarks: [],
  });
  const [finalResult, setFinalResult] = useState<FinalResult | null>(null);
  const [wsError, setWsError] = useState<string>("");

  // -------------------------------------------------------------------------
  // Fetch available exercises from single source of truth (GET /api/analysis/exercises)
  // -------------------------------------------------------------------------
  const loadExercises = useCallback(async () => {
    setExercisesLoading(true);
    setExercisesError("");
    try {
      const list = await fetchExercises();
      setExercises(list);
      if (list && list.length > 0) {
        // Prefer elbow_flexion if present for backward compatibility, else select first
        const defaultEx = list.find((e) => e.id === "elbow_flexion") || list[0];
        setSelectedExercise(defaultEx);
      } else {
        setSelectedExercise(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setExercisesError(msg || "Failed to load rehabilitation exercises.");
      setSelectedExercise(null);
    } finally {
      setExercisesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadExercises();
  }, [loadExercises]);

  // -------------------------------------------------------------------------
  // Cleanup helpers
  // -------------------------------------------------------------------------
  const stopFrameLoop = useCallback(() => {
    if (frameTimerRef.current !== null) {
      clearInterval(frameTimerRef.current);
      frameTimerRef.current = null;
    }
  }, []);

  const closeWebSocket = useCallback((sendEndFirst?: boolean) => {
    const ws = wsRef.current;
    if (!ws) return;
    if (sendEndFirst && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: "END_SESSION" }));
      } catch {
        // ignore
      }
    }
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
    wsRef.current = null;
  }, []);

  const stopCameraStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setStream(null);
    setCameraStatus("idle");
  }, []);

  // Full teardown - stop frame loop, close WS, stop camera
  const fullTeardown = useCallback(
    (sendEndFirst?: boolean) => {
      stopFrameLoop();
      closeWebSocket(sendEndFirst);
      stopCameraStream();
    },
    [stopFrameLoop, closeWebSocket, stopCameraStream]
  );

  // Cleanup on unmount - guaranteed track and timer disposal
  useEffect(() => {
    return () => {
      if (endSessionResolveRef.current) {
        endSessionResolveRef.current();
        endSessionResolveRef.current = null;
      }
      stopFrameLoop();
      closeWebSocket(false);
      stopCameraStream();
    };
  }, [stopFrameLoop, closeWebSocket, stopCameraStream]);

  // -------------------------------------------------------------------------
  // Frame capture loop with backpressure guard
  // -------------------------------------------------------------------------
  const startFrameLoop = useCallback((ws: WebSocket) => {
    // Prevent duplicate timers
    stopFrameLoop();

    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = CANVAS_WIDTH;
    canvas.height = CANVAS_HEIGHT;

    const send = () => {
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      // Flow control / backpressure: avoid unbounded queueing if network/backend is lagging
      if (ws.bufferedAmount > MAX_BUFFERED_AMOUNT) return;
      if (!video.videoWidth || !video.videoHeight) return;

      ctx.drawImage(video, 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
      const dataUrl = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
      try {
        ws.send(dataUrl);
      } catch {
        // WS closed mid-send - the onclose/onerror handler will handle teardown
      }
    };

    frameTimerRef.current = setInterval(send, FRAME_INTERVAL_MS);
  }, [stopFrameLoop]);

  // -------------------------------------------------------------------------
  // WebSocket setup
  // -------------------------------------------------------------------------
  const openWebSocket = useCallback(
    (sid: string) => {
      const url = getWebSocketUrl(sid);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsError("");
        startFrameLoop(ws);
      };

      ws.onmessage = (ev) => {
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }

        switch (msg.type) {
          case "ANALYSIS_RESULT": {
            const rom = (msg.rom as Record<string, number | null>) ?? {};
            const ps = msg.pose_status as Record<string, any> | undefined;
            const isOk = ps?.is_valid !== false && msg.valid_angle != null;

            // Retain cumulative statistics (repetitions, rom, state) across invalid frames
            setLiveStats((prev) => ({
              repetitions: typeof msg.repetitions === "number" ? msg.repetitions : prev.repetitions,
              state: typeof msg.state === "string" ? msg.state : prev.state,
              romMin: typeof rom.min_angle === "number" ? rom.min_angle : prev.romMin,
              romMax: typeof rom.max_angle === "number" ? rom.max_angle : prev.romMax,
              rawAngle: isOk && typeof msg.raw_angle === "number" ? msg.raw_angle : null,
              smoothedAngle: isOk && typeof msg.smoothed_angle === "number" ? msg.smoothed_angle : null,
            }));

            const code: PoseStatusCode = (ps?.status as PoseStatusCode) || (isOk ? "VALID" : "LOW_VISIBILITY");
            setPoseFeedback({
              code: code,
              message: ps?.message || (code === "VALID" ? "Pose tracking active" : "Unreliable joint angle measurement"),
              missingLandmarks: (ps?.missing_landmarks as string[]) || [],
              lowVisibilityLandmarks: (ps?.low_visibility_landmarks as string[]) || [],
            });
            setPoseStatus(isOk ? "ok" : "missing");
            break;
          }
          case "NO_POSE": {
            const code: PoseStatusCode = (msg.status as PoseStatusCode) || "NO_PERSON_DETECTED";
            setPoseFeedback({
              code: code,
              message: (msg.message as string) || "No pose detected. Please step into camera view.",
              missingLandmarks: (msg.missing_landmarks as string[]) || [],
              lowVisibilityLandmarks: (msg.low_visibility_landmarks as string[]) || [],
            });
            setPoseStatus("missing");
            // Preserve cumulative metrics; set angles to null during tracking loss
            setLiveStats((prev) => ({
              ...prev,
              rawAngle: null,
              smoothedAngle: null,
            }));
            break;
          }
          case "ANALYSIS_ERROR": {
            setPoseFeedback({
              code: "ERROR",
              message: (msg.message as string) || "Pose analysis error.",
              missingLandmarks: [],
              lowVisibilityLandmarks: [],
            });
            setPoseStatus("error");
            break;
          }
          case "SESSION_REJECTED": {
            setWsError((msg.message as string) ?? "Session rejected by server.");
            stopFrameLoop();
            stopCameraStream();
            setSessionStatus("error");
            setSessionId(null);
            setActiveSessionExercise(null);
            break;
          }
          case "FINAL_RESULT": {
            const res: FinalResult = {
              repetitions: (msg.repetitions as number) ?? 0,
              romMin: (msg.rom_min as number | null) ?? null,
              romMax: (msg.rom_max as number | null) ?? null,
              romAverage: (msg.rom_average as number | null) ?? null,
              performanceScore: (msg.performance_score as number) ?? 0,
              feedback: (msg.feedback as string) ?? "",
            };
            const currentSid = (msg.session_id as string) || sessionId;
            if (currentSid) {
              pendingFinalResultRef.current = { sessionId: currentSid, result: res };
            }
            setFinalResult(res);
            setSessionStatus("completed");
            if (endSessionResolveRef.current) {
              endSessionResolveRef.current();
              endSessionResolveRef.current = null;
            }
            break;
          }
        }
      };

      ws.onerror = () => {
        setWsError("WebSocket connection error. Check that the backend is running.");
        stopFrameLoop();
        stopCameraStream();
        setSessionStatus("error");
        if (endSessionResolveRef.current) {
          endSessionResolveRef.current();
          endSessionResolveRef.current = null;
        }
      };

      ws.onclose = () => {
        stopFrameLoop();
        // If WebSocket disconnects unexpectedly while active (not during intentional ending/completed)
        if (sessionStatusRef.current === "active") {
          stopCameraStream();
          setWsError("Live tracking connection lost. Please check your network or server.");
          setSessionStatus("error");
          setIsActionLoading(false);
        }
        if (endSessionResolveRef.current) {
          endSessionResolveRef.current();
          endSessionResolveRef.current = null;
        }
      };
    },
    [startFrameLoop, stopFrameLoop, stopCameraStream]
  );

  // -------------------------------------------------------------------------
  // Session start (dynamic exercise selection with concurrency guard)
  // -------------------------------------------------------------------------
  const handleStartSession = async () => {
    if (
      isActionLoading ||
      !selectedExercise ||
      sessionStatus === "starting" ||
      sessionStatus === "active" ||
      sessionStatus === "ending"
    ) {
      return;
    }
    setIsActionLoading(true);
    setSessionStatus("starting");
    fullTeardown(false);
    setFinalResult(null);
    pendingFinalResultRef.current = null;
    setWsError("");
    setLiveStats({ repetitions: 0, rawAngle: null, smoothedAngle: null, state: "-", romMin: null, romMax: null });
    setPoseFeedback({
      code: "VALID",
      message: "Initializing pose tracking...",
      missingLandmarks: [],
      lowVisibilityLandmarks: [],
    });
    setCameraStatus("loading");
    setCameraError("");

    let acquiredStream: MediaStream | null = null;

    try {
      // 1. Snapshot active exercise before starting session
      const currentExercise = selectedExercise;
      setActiveSessionExercise(currentExercise);
      setActiveSessionSide(selectedSide);

      // 2. Acquire camera stream
      acquiredStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });

      streamRef.current = acquiredStream;
      setStream(acquiredStream);
      if (videoRef.current) {
        videoRef.current.srcObject = acquiredStream;
      }
      setCameraStatus("active");

      // 3. Create backend session with explicit selected exercise id and side
      const response = await startSession("P001", currentExercise.id, selectedSide);
      const sid: string = response.session_id;
      setSessionId(sid);
      setSessionStatus("active");

      // 4. Open WebSocket using returned session_id
      openWebSocket(sid);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      stopCameraStream();
      closeWebSocket(false);
      stopFrameLoop();
      setCameraStatus("error");
      setCameraError(
        msg.includes("getUserMedia") || msg.includes("Camera") || msg.includes("permission")
          ? "Camera access denied or device not found. Please allow camera permissions."
          : `Error: ${msg}`
      );
      setSessionStatus("error");
      setSessionId(null);
      setActiveSessionExercise(null);
    } finally {
      setIsActionLoading(false);
    }
  };

  // -------------------------------------------------------------------------
  // Session end (normal flow)
  // -------------------------------------------------------------------------
  const handleEndSession = async () => {
    if (isActionLoading || !sessionId || sessionStatus === "ending") return;
    setIsActionLoading(true);
    setSessionStatus("ending");

    const currentSessionId = sessionId;
    // Clear any previous session's pending result to prevent stale cross-session population
    if (pendingFinalResultRef.current?.sessionId !== currentSessionId) {
      pendingFinalResultRef.current = null;
    }

    // 1. Stop sending new frames
    stopFrameLoop();

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      // 2. Send END_SESSION and wait for FINAL_RESULT from WebSocket
      await new Promise<void>((resolve) => {
        let timer: ReturnType<typeof setTimeout> | null = null;
        const finish = () => {
          if (timer !== null) {
            clearTimeout(timer);
            timer = null;
          }
          endSessionResolveRef.current = null;
          resolve();
        };

        endSessionResolveRef.current = finish;
        timer = setTimeout(finish, 3000);

        try {
          ws.send(JSON.stringify({ type: "END_SESSION" }));
        } catch {
          finish();
        }
      });
    }

    // 3. Teardown WS + Camera
    closeWebSocket(false);
    stopCameraStream();

    // 4. Call authoritative REST /sessions/{id}/end to mark COMPLETED
    let endRes: any = null;
    let endError: string | null = null;
    try {
      endRes = await endSession(currentSessionId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      endError = msg;
      console.warn("REST endSession warning:", err);
    }

    // 5. Determine final result for THIS session safely
    if (pendingFinalResultRef.current?.sessionId === currentSessionId) {
      // WebSocket already delivered FINAL_RESULT for this session
      setFinalResult(pendingFinalResultRef.current.result);
      setSessionStatus("completed");
    } else if (endRes && endRes.result) {
      // Fallback: REST /end provided persisted result
      setFinalResult({
        repetitions: endRes.result.repetitions ?? 0,
        romMin: endRes.result.rom_min ?? null,
        romMax: endRes.result.rom_max ?? null,
        romAverage: endRes.result.rom_average ?? null,
        performanceScore: endRes.result.performance_score ?? 0,
        feedback: endRes.result.feedback ?? "",
      });
      setSessionStatus("completed");
    } else {
      // No result received or persisted (e.g. 4xx no-result condition)
      setFinalResult(null);
      if (endError) {
        setWsError(
          endError.includes("no result")
            ? "Session ended without recorded exercise data. No final results were generated."
            : `Session finalization error: ${endError}`
        );
        setSessionStatus("error");
      } else {
        setSessionStatus("idle");
      }
    }

    setSessionId(null);
    setIsActionLoading(false);
  };

  // -------------------------------------------------------------------------
  // Render helpers
  // -------------------------------------------------------------------------
  const formatAngle = (v: number | null) =>
    v !== null ? `${v.toFixed(1)}°` : "-";

  const scoreColor =
    finalResult === null
      ? ""
      : finalResult.performanceScore >= 80
      ? "text-emerald-500"
      : finalResult.performanceScore >= 50
      ? "text-amber-500"
      : "text-red-500";

  // Active exercise for display (snapshots during active session)
  const displayExercise =
    sessionStatus === "active" || sessionStatus === "ending"
      ? activeSessionExercise
      : selectedExercise;

  // -------------------------------------------------------------------------
  // JSX
  // -------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-background font-sans flex flex-col">
      {/* Offscreen canvas for frame capture */}
      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

      {/* Header */}
      <header className="flex items-center justify-between border-b border-border/40 bg-card/50 px-6 py-4 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="flex size-10 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shadow-sm cursor-pointer"
          >
            <ArrowLeft className="size-5" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-emerald-600 dark:text-emerald-400 tracking-tight flex items-center gap-2">
              <Activity className="size-5" />
              Patient Portal
            </h1>
            <p className="text-sm text-muted-foreground">Live Rehabilitation Session</p>
          </div>
        </div>

        {sessionStatus === "active" && (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex flex-col items-end mr-4">
              <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Session ID</span>
              <span className="text-sm font-mono text-foreground font-bold">{sessionId}</span>
            </div>
            <span className="flex items-center gap-1.5 rounded-full bg-success/10 border border-success/20 px-3 py-1 text-xs font-bold text-success-foreground">
              <span className="size-2 rounded-full bg-success animate-pulse" />
              LIVE
            </span>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 flex flex-col items-center max-w-6xl mx-auto w-full gap-6">

        {/* Dynamic Exercise Title & Description */}
        <div className="w-full text-center space-y-2">
          <h2 className="text-2xl font-bold text-foreground">
            {displayExercise ? displayExercise.name : "Rehabilitation Session"}
          </h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            {displayExercise
              ? displayExercise.description
              : "Select a rehabilitation exercise below to get started."}
          </p>
        </div>

        {/* Exercise Selection UI (Visible when idle, completed, or after error) */}
        {(sessionStatus === "idle" || sessionStatus === "completed" || sessionStatus === "error") && (
          <div className="w-full max-w-4xl space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Select Rehabilitation Exercise &amp; Side
              </h3>
              <div className="flex items-center gap-3">
                {selectedExercise && (
                  <span className="text-xs text-muted-foreground hidden sm:inline">
                    Selected: <strong className="text-emerald-500 font-semibold">{selectedExercise.name}</strong>
                  </span>
                )}
                <div className="inline-flex rounded-xl bg-muted/60 p-1 border border-border">
                  <button
                    type="button"
                    onClick={() => setSelectedSide("left")}
                    id="btn-side-left"
                    className={`px-3 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                      selectedSide === "left"
                        ? "bg-emerald-500 text-white shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Left
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedSide("right")}
                    id="btn-side-right"
                    className={`px-3 py-1 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                      selectedSide === "right"
                        ? "bg-emerald-500 text-white shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Right
                  </button>
                </div>
              </div>
            </div>

            {exercisesLoading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-28 rounded-2xl border border-border/50 bg-muted/20 animate-pulse" />
                ))}
              </div>
            ) : exercisesError ? (
              <div className="flex items-center justify-between bg-destructive/10 border border-destructive/30 rounded-2xl p-4 text-sm text-destructive">
                <div className="flex items-center gap-2">
                  <AlertCircle className="size-4 shrink-0" />
                  <span>{exercisesError}</span>
                </div>
                <button
                  type="button"
                  onClick={loadExercises}
                  className="flex items-center gap-1 font-bold underline hover:opacity-80 cursor-pointer"
                >
                  <RotateCcw className="size-3.5" />
                  Retry
                </button>
              </div>
            ) : exercises.length === 0 ? (
              <div className="rounded-2xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
                No rehabilitation exercises available.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {exercises.map((ex) => {
                  const isSelected = selectedExercise?.id === ex.id;
                  return (
                    <button
                      key={ex.id}
                      type="button"
                      onClick={() => setSelectedExercise(ex)}
                      className={`p-4 rounded-2xl border text-left transition-all duration-200 cursor-pointer flex flex-col justify-between gap-3 ${
                        isSelected
                          ? "bg-emerald-500/10 border-emerald-500 shadow-md ring-1 ring-emerald-500/30 text-foreground scale-[1.02]"
                          : "bg-card border-border hover:border-border/80 hover:bg-muted/40 text-muted-foreground"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className={`text-sm font-bold ${isSelected ? "text-emerald-500" : "text-foreground"}`}>
                            {ex.name}
                          </span>
                          {isSelected && (
                            <span className="size-2 rounded-full bg-emerald-500" />
                          )}
                        </div>
                        <p className="text-xs line-clamp-2 leading-relaxed opacity-80">
                          {ex.description}
                        </p>
                      </div>
                      <div className="pt-2 border-t border-border/40 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider">
                        <span className="text-muted-foreground">{ex.joint_angle.replace("left_", "").replace("_", " ")}</span>
                        <span className="text-emerald-500/90 font-mono">{ex.movement_type.replace("_", " ")}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Active Exercise Status Indicator during Live Session */}
        {(sessionStatus === "active" || sessionStatus === "ending") && activeSessionExercise && (
          <div className="w-full max-w-4xl flex items-center justify-between bg-card border border-border rounded-2xl px-5 py-3 shadow-sm">
            <div className="flex items-center gap-3">
              <span className="size-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-sm font-medium text-muted-foreground">
                Active Exercise:{" "}
                <span className="font-bold text-foreground">
                  {activeSessionExercise.name} ({activeSessionSide.toUpperCase()})
                </span>
              </span>
            </div>
            <span className="text-xs font-mono uppercase bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 px-2.5 py-1 rounded-full font-semibold">
              {activeSessionExercise.joint_angle.replace("left_", `${activeSessionSide}_`)}
            </span>
          </div>
        )}

        {/* WS / session error banner */}
        {wsError && (
          <div className="w-full max-w-4xl flex items-center gap-3 bg-destructive/10 border border-destructive/30 rounded-xl px-4 py-3 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            {wsError}
          </div>
        )}

        {/* Camera + Live Stats row */}
        <div className="w-full max-w-4xl flex flex-col lg:flex-row gap-6">

          {/* Camera */}
          <div className="relative flex-1 aspect-video rounded-3xl overflow-hidden border-2 border-border/50 bg-card shadow-2xl flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`absolute inset-0 w-full h-full object-cover transform -scale-x-100 transition-opacity duration-500 ${cameraStatus === "active" ? "opacity-100" : "opacity-0"}`}
            />

            {cameraStatus === "idle" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-muted/20 backdrop-blur-sm gap-4 text-muted-foreground z-10">
                <div className="p-5 rounded-full bg-background border border-border shadow-sm">
                  <CameraOff className="size-8 opacity-50" />
                </div>
                <p className="font-medium text-lg">Camera is inactive</p>
                <p className="text-sm opacity-70 max-w-sm text-center">Click Start Session below to enable your camera and begin rehabilitation tracking.</p>
              </div>
            )}

            {cameraStatus === "loading" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md gap-4 z-10">
                <Loader2 className="size-10 text-emerald-500 animate-spin" />
                <p className="font-medium text-foreground">Accessing secure camera feed...</p>
                <p className="text-sm text-muted-foreground">Please allow camera permissions if prompted.</p>
              </div>
            )}

            {cameraStatus === "error" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-destructive/5 backdrop-blur-md gap-4 z-10">
                <div className="p-4 rounded-full bg-destructive/10 text-destructive border border-destructive/20">
                  <AlertCircle className="size-8" />
                </div>
                <p className="font-bold text-destructive text-lg">Camera Access Failed</p>
                <p className="text-sm text-muted-foreground max-w-md text-center">{cameraError}</p>
              </div>
            )}

            {/* REC indicator */}
            {cameraStatus === "active" && sessionStatus === "active" && (
              <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/50 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 z-20">
                <span className="size-2.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-xs font-medium tracking-wide text-white drop-shadow-sm">REC</span>
              </div>
            )}

            {/* Pose status indicator */}
            {sessionStatus === "active" && cameraStatus === "active" && (
              <div className="absolute top-4 right-4 z-20 flex items-center gap-2">
                <span
                  id="pose-status-badge"
                  className={`text-xs font-bold px-3 py-1 rounded-full border backdrop-blur-md transition-colors ${
                    poseFeedback.code === "VALID"
                      ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                      : poseFeedback.code === "NO_PERSON_DETECTED"
                      ? "bg-amber-500/20 border-amber-500/40 text-amber-300"
                      : poseFeedback.code === "REQUIRED_LANDMARKS_MISSING"
                      ? "bg-amber-500/20 border-amber-500/40 text-amber-300"
                      : poseFeedback.code === "LOW_VISIBILITY"
                      ? "bg-orange-500/20 border-orange-500/40 text-orange-300"
                      : poseFeedback.code === "INVALID_ANGLE"
                      ? "bg-rose-500/20 border-rose-500/40 text-rose-300"
                      : "bg-red-500/20 border-red-500/40 text-red-300"
                  }`}
                >
                  {poseFeedback.code === "VALID"
                    ? "POSE OK"
                    : poseFeedback.code === "NO_PERSON_DETECTED"
                    ? "NO PERSON"
                    : poseFeedback.code === "REQUIRED_LANDMARKS_MISSING"
                    ? "LANDMARKS MISSING"
                    : poseFeedback.code === "LOW_VISIBILITY"
                    ? "LOW CONFIDENCE"
                    : poseFeedback.code === "INVALID_ANGLE"
                    ? "INVALID POSE"
                    : "TRACKING ERROR"}
                </span>
              </div>
            )}

            {/* Live pose guidance banner */}
            {sessionStatus === "active" && cameraStatus === "active" && poseFeedback.code !== "VALID" && (
              <div
                id="pose-guidance-banner"
                className="absolute bottom-4 left-4 right-4 z-20 flex items-center gap-2.5 bg-background/90 backdrop-blur-md border border-amber-500/30 rounded-xl px-3.5 py-2 text-xs font-medium text-amber-300 shadow-lg animate-in fade-in duration-200"
              >
                <AlertCircle className="size-4 shrink-0 text-amber-400" />
                <span className="leading-snug">{poseFeedback.message}</span>
              </div>
            )}

            {/* Ending overlay */}
            {sessionStatus === "ending" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md gap-4 z-20">
                <Loader2 className="size-10 text-emerald-500 animate-spin" />
                <p className="font-medium text-foreground">Finalising session...</p>
              </div>
            )}
          </div>

          {/* Live stats panel */}
          {(sessionStatus === "active" || sessionStatus === "ending") && (
            <div className="lg:w-56 flex flex-col gap-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Live Metrics</h3>
              <StatCard label="Repetitions" value={String(liveStats.repetitions)} accent="emerald" />
              <StatCard label="Smoothed Angle" value={formatAngle(liveStats.smoothedAngle)} accent="blue" />
              <StatCard label="Phase" value={liveStats.state} accent="violet" />
              <StatCard label="ROM Min" value={formatAngle(liveStats.romMin)} accent="amber" />
              <StatCard label="ROM Max" value={formatAngle(liveStats.romMax)} accent="amber" />
            </div>
          )}
        </div>

        {/* Final result panel */}
        {finalResult && sessionStatus === "completed" && (
          <div className="w-full max-w-4xl bg-card border border-border rounded-3xl p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="size-6 text-emerald-500" />
                <h3 className="text-xl font-bold text-foreground">Session Summary</h3>
              </div>
              {(activeSessionExercise || selectedExercise) && (
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400">
                  {(activeSessionExercise || selectedExercise)?.name} ({activeSessionSide.toUpperCase()})
                </span>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <SummaryCard label="Repetitions" value={String(finalResult.repetitions)} />
              <SummaryCard label="Score" value={`${finalResult.performanceScore.toFixed(1)}%`} valueClass={scoreColor} />
              <SummaryCard label="ROM Min" value={formatAngle(finalResult.romMin)} />
              <SummaryCard label="ROM Max" value={formatAngle(finalResult.romMax)} />
            </div>
            {finalResult.feedback && (
              <p className="text-sm text-muted-foreground border-t border-border pt-3">{finalResult.feedback}</p>
            )}
            <button
              onClick={() => {
                setSessionStatus("idle");
                setFinalResult(null);
                setActiveSessionExercise(null);
              }}
              className="text-sm font-semibold text-emerald-600 hover:text-emerald-500 transition-colors cursor-pointer"
            >
              Start a new session
            </button>
          </div>
        )}

        {/* Controls */}
        <div className="flex flex-wrap justify-center gap-4 w-full max-w-md">
          {sessionStatus === "idle" || sessionStatus === "completed" || sessionStatus === "error" ? (
            <button
              onClick={handleStartSession}
              disabled={isActionLoading || !selectedExercise || exercisesLoading || exercises.length === 0}
              id="btn-start-session"
              className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-8 py-4 font-bold text-white shadow-lg hover:bg-emerald-500 hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 cursor-pointer"
            >
              {isActionLoading ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Play className="size-5 fill-current" />
              )}
              {sessionStatus === "error" ? "Retry Session" : "Start Rehab Session"}
            </button>
          ) : (
            <button
              onClick={handleEndSession}
              disabled={isActionLoading || sessionStatus === "ending"}
              id="btn-end-session"
              className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-destructive px-8 py-4 font-bold text-white shadow-lg hover:bg-destructive/90 hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 cursor-pointer"
            >
              {isActionLoading ? <Loader2 className="size-5 animate-spin" /> : <Square className="size-5 fill-current" />}
              End Session
            </button>
          )}
        </div>

      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small presentational sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  const accentMap: Record<string, string> = {
    emerald: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
    blue: "bg-blue-500/10 border-blue-500/20 text-blue-400",
    violet: "bg-violet-500/10 border-violet-500/20 text-violet-400",
    amber: "bg-amber-500/10 border-amber-500/20 text-amber-400",
  };
  return (
    <div className={`rounded-2xl border px-4 py-3 ${accentMap[accent] ?? accentMap.emerald}`}>
      <p className="text-[10px] uppercase font-bold tracking-wider opacity-60">{label}</p>
      <p className="text-xl font-mono font-bold mt-0.5">{value}</p>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  valueClass = "",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-muted/30 px-4 py-3 text-center">
      <p className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">{label}</p>
      <p className={`text-2xl font-mono font-bold mt-1 ${valueClass || "text-foreground"}`}>{value}</p>
    </div>
  );
}
