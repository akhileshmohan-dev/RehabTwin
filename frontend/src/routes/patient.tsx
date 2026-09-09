import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState, useMemo } from "react";
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
  User,
  Search,
  Dumbbell,
  Target,
  Clock,
  LogOut,
  ChevronRight,
  FileText,
} from "lucide-react";
import {
  fetchPatients,
  fetchPatientAssignments,
  fetchPatientSessions,
  startSession,
  endSession,
  getWebSocketUrl,
} from "@/data/rehabService";
import type { Patient, PatientAssignment, Session } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";

export const Route = createFileRoute("/patient")({
  head: () => ({
    meta: [
      { title: "RehabTwin — Patient Portal" },
      {
        name: "description",
        content: "Patient rehabilitation portal for guided exercises, prescribed assignments, and AI camera tracking.",
      },
    ],
  }),
  component: PatientPortal,
});

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type CameraStatus = "idle" | "loading" | "active" | "error";
type SessionStatus = "idle" | "preparing" | "active" | "finalizing" | "completed" | "error";

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
const MAX_BUFFERED_AMOUNT = 65536;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
function PatientPortal() {
  // Screen / selection navigation
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [selectedAssignment, setSelectedAssignment] = useState<PatientAssignment | null>(null);

  // Directory state
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [patientsError, setPatientsError] = useState("");
  const [patientSearch, setPatientSearch] = useState("");

  // Patient assignments & history state
  const [assignments, setAssignments] = useState<PatientAssignment[]>([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);
  const [assignmentsError, setAssignmentsError] = useState("");
  const [historySessions, setHistorySessions] = useState<Session[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Live session & camera refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const frameTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const endSessionResolveRef = useRef<(() => void) | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sessionStatusRef = useRef<SessionStatus>("idle");
  const pendingFinalResultRef = useRef<{ sessionId: string; result: FinalResult } | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Session state
  const [, setStream] = useState<MediaStream | null>(null);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("idle");
  const [cameraError, setCameraError] = useState<string>("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionCompletedAt, setSessionCompletedAt] = useState<string | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Keep sessionStatusRef in sync
  useEffect(() => {
    sessionStatusRef.current = sessionStatus;
  }, [sessionStatus]);

  // Live metrics & feedback
  const [liveStats, setLiveStats] = useState<LiveStats>({
    repetitions: 0,
    rawAngle: null,
    smoothedAngle: null,
    state: "-",
    romMin: null,
    romMax: null,
  });
  const [poseFeedback, setPoseFeedback] = useState<PoseFeedback>({
    code: "VALID",
    message: "Pose tracking active",
    missingLandmarks: [],
    lowVisibilityLandmarks: [],
  });
  const [finalResult, setFinalResult] = useState<FinalResult | null>(null);
  const [wsError, setWsError] = useState<string>("");

  // -------------------------------------------------------------------------
  // 1. Fetch patients list for Screen 1
  // -------------------------------------------------------------------------
  const loadPatients = useCallback(async () => {
    setPatientsLoading(true);
    setPatientsError("");
    try {
      const list = await fetchPatients();
      // Show active patients, or all if none specifically active
      setPatients(list);
    } catch (err: any) {
      setPatientsError(err.message || "Failed to load patient directory.");
    } finally {
      setPatientsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  // -------------------------------------------------------------------------
  // 2. Fetch assignments & history when patient is selected
  // -------------------------------------------------------------------------
  const loadPatientData = useCallback(async (patientId: string) => {
    setAssignmentsLoading(true);
    setAssignmentsError("");
    setHistoryLoading(true);

    try {
      const [assigns, sessions] = await Promise.all([
        fetchPatientAssignments(patientId),
        fetchPatientSessions(patientId),
      ]);
      setAssignments(assigns);
      setHistorySessions(sessions);
    } catch (err: any) {
      setAssignmentsError(err.message || "Failed to load patient plan.");
    } finally {
      setAssignmentsLoading(false);
      setHistoryLoading(false);
    }
  }, []);

  const handleSelectPatient = (patient: Patient) => {
    setSelectedPatient(patient);
    setSelectedAssignment(null);
    setSessionStatus("idle");
    setFinalResult(null);
    loadPatientData(patient.id);
  };

  const handleSwitchPatient = () => {
    fullTeardown(false);
    setSelectedPatient(null);
    setSelectedAssignment(null);
    setSessionStatus("idle");
    setFinalResult(null);
    setSessionId(null);
    setSessionCompletedAt(null);
    setWsError("");
    setCameraError("");
    loadPatients();
  };

  // Filtered patient directory
  const filteredPatients = useMemo(() => {
    const q = patientSearch.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        (p.name && p.name.toLowerCase().includes(q))
    );
  }, [patients, patientSearch]);

  // Filter active assignments only
  const activeAssignments = useMemo(() => {
    return assignments.filter((a) => a.active);
  }, [assignments]);

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

  const fullTeardown = useCallback(
    (sendEndFirst?: boolean) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      stopFrameLoop();
      closeWebSocket(sendEndFirst);
      stopCameraStream();
    },
    [stopFrameLoop, closeWebSocket, stopCameraStream]
  );

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
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
      if (ws.bufferedAmount > MAX_BUFFERED_AMOUNT) return;
      if (!video.videoWidth || !video.videoHeight) return;

      ctx.drawImage(video, 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
      const dataUrl = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
      try {
        ws.send(dataUrl);
      } catch {
        // WS closed mid-send
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
            break;
          }
          case "SESSION_REJECTED": {
            setWsError((msg.message as string) ?? "Session rejected by server.");
            stopFrameLoop();
            stopCameraStream();
            setSessionStatus("error");
            setSessionId(null);
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
            // CRITICAL: Set UI state to "finalizing", NOT "completed".
            // The session is only COMPLETED once authoritative REST /end has committed!
            setSessionStatus("finalizing");
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
    [startFrameLoop, stopFrameLoop, stopCameraStream, sessionId]
  );

  // -------------------------------------------------------------------------
  // 3. Start Session (Authoritative assignment_id)
  // -------------------------------------------------------------------------
  const handleStartSession = async () => {
    if (
      isActionLoading ||
      !selectedPatient ||
      !selectedAssignment ||
      sessionStatus === "preparing" ||
      sessionStatus === "active" ||
      sessionStatus === "finalizing"
    ) {
      return;
    }

    setIsActionLoading(true);
    setSessionStatus("preparing");
    fullTeardown(false);
    setFinalResult(null);
    setSessionCompletedAt(null);
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
      // 1. Acquire camera stream
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

      // 2. Start session authoritatively with patientId and assignmentId
      const response = await startSession(selectedPatient.id, selectedAssignment.id);
      const sid: string = response.session_id;
      setSessionId(sid);
      setSessionStatus("active");

      // 3. Open WebSocket for live analysis
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
          : `Error starting session: ${msg}`
      );
      setSessionStatus("error");
      setSessionId(null);
    } finally {
      setIsActionLoading(false);
    }
  };

  // -------------------------------------------------------------------------
  // 4. End Session (Authoritative REST /end)
  // -------------------------------------------------------------------------
  const handleEndSession = async () => {
    if (isActionLoading || !sessionId || sessionStatus === "finalizing") return;
    setIsActionLoading(true);
    setSessionStatus("finalizing");

    const currentSessionId = sessionId;
    if (pendingFinalResultRef.current?.sessionId !== currentSessionId) {
      pendingFinalResultRef.current = null;
    }

    stopFrameLoop();

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
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

    closeWebSocket(false);
    stopCameraStream();

    let endRes: any = null;
    let endError: string | null = null;
    try {
      endRes = await endSession(currentSessionId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      endError = msg;
      console.warn("REST endSession warning:", err);
    }

    // Only mark completed if REST /end succeeded and result exists
    if (!endError && (endRes?.result || pendingFinalResultRef.current?.sessionId === currentSessionId)) {
      const r = endRes?.result || pendingFinalResultRef.current?.result;
      setFinalResult({
        repetitions: r.repetitions ?? 0,
        romMin: r.rom_min ?? r.romMin ?? null,
        romMax: r.rom_max ?? r.romMax ?? null,
        romAverage: r.rom_average ?? r.romAverage ?? null,
        performanceScore: r.performance_score ?? r.performanceScore ?? 0,
        feedback: r.feedback ?? "",
      });
      setSessionCompletedAt(new Date().toISOString());
      setSessionStatus("completed");
      setSessionId(null);
    } else {
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
        setSessionId(null);
      }
    }

    setIsActionLoading(false);

    // Refresh history in background
    if (selectedPatient) {
      loadPatientData(selectedPatient.id);
    }
  };

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

  // -------------------------------------------------------------------------
  // RENDER: SCREEN 1 — SELECT PATIENT
  // -------------------------------------------------------------------------
  if (!selectedPatient) {
    return (
      <div className="min-h-screen bg-background font-sans flex flex-col">
        <header className="border-b border-border/40 bg-card/50 px-6 py-4 backdrop-blur-md sticky top-0 z-10 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/"
              className="flex size-10 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shadow-sm"
            >
              <ArrowLeft className="size-5" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-emerald-600 dark:text-emerald-400 tracking-tight flex items-center gap-2">
                <Activity className="size-5" />
                Patient Portal
              </h1>
              <p className="text-xs text-muted-foreground">Select your profile to begin rehabilitation</p>
            </div>
          </div>
        </header>

        <main className="flex-1 p-6 flex flex-col items-center max-w-3xl mx-auto w-full gap-6">
          <div className="text-center space-y-2 mt-4">
            <div className="inline-flex size-14 items-center justify-center rounded-2xl bg-primary-soft text-primary border border-primary/20 mb-2">
              <User className="size-7" />
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">Select Your Patient Profile</h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Choose your profile to access your personalized rehabilitation plan and start your assigned therapy.
            </p>
          </div>

          <div className="w-full relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <input
              type="text"
              value={patientSearch}
              onChange={(e) => setPatientSearch(e.target.value)}
              placeholder="Search by your name or patient ID..."
              className="w-full rounded-2xl border border-border bg-card py-3 pl-10 pr-4 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all shadow-xs"
            />
          </div>

          {patientsError && (
            <div className="w-full flex items-center justify-between bg-destructive/10 border border-destructive/30 rounded-2xl p-4 text-sm text-destructive">
              <div className="flex items-center gap-2">
                <AlertCircle className="size-4 shrink-0" />
                <span>{patientsError}</span>
              </div>
              <button
                type="button"
                onClick={loadPatients}
                className="flex items-center gap-1 font-bold underline hover:opacity-80"
              >
                <RotateCcw className="size-3.5" />
                Retry
              </button>
            </div>
          )}

          <div className="w-full space-y-3">
            {patientsLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-20 rounded-2xl border border-border bg-card/50 animate-pulse" />
                ))}
              </div>
            ) : filteredPatients.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border bg-card/50 p-8 text-center space-y-2">
                <User className="size-10 text-muted-foreground/40 mx-auto" />
                <p className="text-sm font-medium text-foreground">No matching patients found</p>
                <p className="text-xs text-muted-foreground">
                  If you are a new patient, please request your therapist to register you in the system.
                </p>
              </div>
            ) : (
              filteredPatients.map((patient) => (
                <button
                  key={patient.id}
                  type="button"
                  onClick={() => handleSelectPatient(patient)}
                  className="w-full rounded-2xl border border-border bg-card p-4 text-left hover:border-primary hover:bg-primary-soft/30 transition-all shadow-card flex items-center justify-between gap-4 group"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex size-12 items-center justify-center rounded-xl bg-secondary text-sm font-bold text-secondary-foreground font-sans border border-border/40">
                      {patient.id}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-base text-foreground group-hover:text-primary transition-colors">
                          {patient.name}
                        </span>
                        {patient.status === "INACTIVE" && (
                          <span className="text-[10px] rounded-full bg-destructive/10 text-destructive px-2 py-0.5 font-semibold">
                            Inactive
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                        <span>ID: {patient.id}</span>
                        {patient.lastActive && (
                          <span>• Last active: {formatDateTime(patient.lastActive)}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 text-muted-foreground group-hover:text-primary transition-colors">
                    <span className="text-xs font-semibold hidden sm:inline">Select Profile</span>
                    <ChevronRight className="size-4" />
                  </div>
                </button>
              ))
            )}
          </div>
        </main>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // RENDER: SCREEN 2 — ASSIGNED EXERCISES & HISTORY (when no assignment selected)
  // -------------------------------------------------------------------------
  if (!selectedAssignment) {
    return (
      <div className="min-h-screen bg-background font-sans flex flex-col">
        <header className="border-b border-border/40 bg-card/50 px-6 py-4 backdrop-blur-md sticky top-0 z-10 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={handleSwitchPatient}
              className="flex size-10 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shadow-sm"
              title="Switch Patient"
            >
              <ArrowLeft className="size-5" />
            </button>
            <div>
              <h1 className="text-xl font-bold text-emerald-600 dark:text-emerald-400 tracking-tight flex items-center gap-2">
                <Activity className="size-5" />
                Patient Portal
              </h1>
              <p className="text-xs text-muted-foreground">
                Rehabilitation plan for <strong className="text-foreground">{selectedPatient.name}</strong> ({selectedPatient.id})
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleSwitchPatient}
            className="flex items-center gap-1.5 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <LogOut className="size-3.5" />
            <span>Switch Patient</span>
          </button>
        </header>

        <main className="flex-1 p-6 flex flex-col items-center max-w-5xl mx-auto w-full gap-8">
          {/* Active Assignments Section */}
          <div className="w-full space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                  <Dumbbell className="size-5 text-emerald-500" />
                  Your Prescribed Exercises
                </h2>
                <p className="text-xs text-muted-foreground">
                  Select an assigned exercise to begin AI-guided tracking.
                </p>
              </div>
              <span className="text-xs font-semibold text-muted-foreground bg-muted/60 px-3 py-1 rounded-full border border-border">
                {activeAssignments.length} Active {activeAssignments.length === 1 ? "Protocol" : "Protocols"}
              </span>
            </div>

            {assignmentsError && (
              <div className="flex items-center gap-2 rounded-2xl bg-destructive/10 border border-destructive/30 p-4 text-xs text-destructive">
                <AlertCircle className="size-4 shrink-0" />
                <span>{assignmentsError}</span>
              </div>
            )}

            {assignmentsLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {[1, 2].map((i) => (
                  <div key={i} className="h-40 rounded-2xl border border-border bg-card/50 animate-pulse" />
                ))}
              </div>
            ) : activeAssignments.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-amber-500/40 bg-amber-500/5 p-8 text-center space-y-3">
                <div className="flex size-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-500 mx-auto">
                  <AlertCircle className="size-6" />
                </div>
                <h3 className="font-bold text-base text-foreground">No Active Exercise Assignments</h3>
                <p className="text-xs text-muted-foreground max-w-md mx-auto leading-relaxed">
                  Your therapist has not assigned any active rehabilitation protocols to your profile yet.
                  Please consult Dr. Sharma or your clinical team to prescribe an exercise plan.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeAssignments.map((assignment) => (
                  <div
                    key={assignment.id}
                    className="rounded-2xl border border-border bg-card p-5 shadow-card hover:border-emerald-500 transition-all flex flex-col justify-between gap-4"
                  >
                    <div className="space-y-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="font-bold text-lg text-foreground">
                          {assignment.exercise_name || assignment.exercise_id}
                        </h3>
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold uppercase ${
                            assignment.side.toLowerCase() === "right"
                              ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                              : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                          }`}
                        >
                          {assignment.side} Side
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-2 pt-1">
                        <div className="rounded-xl border border-border/60 bg-muted/30 p-2 text-center">
                          <p className="text-[10px] uppercase font-bold text-muted-foreground">Target ROM</p>
                          <p className="text-sm font-bold text-foreground mt-0.5">
                            {assignment.target_rom !== null ? `${assignment.target_rom}°` : "Default"}
                          </p>
                        </div>
                        <div className="rounded-xl border border-border/60 bg-muted/30 p-2 text-center">
                          <p className="text-[10px] uppercase font-bold text-muted-foreground">Target Reps</p>
                          <p className="text-sm font-bold text-foreground mt-0.5">
                            {assignment.target_repetitions !== null ? assignment.target_repetitions : "Default"}
                          </p>
                        </div>
                        <div className="rounded-xl border border-border/60 bg-muted/30 p-2 text-center">
                          <p className="text-[10px] uppercase font-bold text-muted-foreground">Frequency</p>
                          <p className="text-sm font-bold text-foreground mt-0.5">
                            {assignment.sessions_per_day}x / day
                          </p>
                        </div>
                      </div>

                      {assignment.notes && (
                        <p className="text-xs text-muted-foreground italic bg-muted/20 p-2.5 rounded-xl border border-border/40">
                          "{assignment.notes}"
                        </p>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedAssignment(assignment);
                        setSessionStatus("idle");
                        setFinalResult(null);
                      }}
                      className="w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm hover:bg-emerald-500 transition-all btn-interactive"
                    >
                      <Play className="size-4 fill-current" />
                      <span>Start {assignment.exercise_name || assignment.exercise_id}</span>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Session History Section */}
          <div className="w-full space-y-4 pt-4 border-t border-border/60">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                <Clock className="size-4 text-muted-foreground" />
                Your Session History
              </h2>
              <span className="text-xs text-muted-foreground font-medium">
                {historySessions.length} Recorded
              </span>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-border bg-card shadow-card">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs font-semibold text-muted-foreground">
                    <th className="py-3 px-4">Date &amp; Time</th>
                    <th className="py-3 px-4">Exercise</th>
                    <th className="py-3 px-4">Side</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Reps</th>
                    <th className="py-3 px-4">ROM</th>
                    <th className="py-3 px-4">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {historyLoading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-xs text-muted-foreground animate-pulse">
                        Loading session history...
                      </td>
                    </tr>
                  ) : historySessions.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-xs text-muted-foreground">
                        No previous sessions found for this profile.
                      </td>
                    </tr>
                  ) : (
                    historySessions.map((s) => {
                      const isActive = s.status === "ACTIVE";
                      return (
                        <tr key={s.rawSessionId || s.id} className="border-b border-border/40 last:border-0 hover:bg-muted/20">
                          <td className="whitespace-nowrap py-3 px-4 text-xs font-sans text-muted-foreground">
                            {formatDateTime(s.dateTime)}
                          </td>
                          <td className="whitespace-nowrap py-3 px-4 font-semibold text-foreground">
                            {s.exercise}
                          </td>
                          <td className="whitespace-nowrap py-3 px-4">
                            <span
                              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                s.side.toLowerCase() === "right"
                                  ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                                  : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              }`}
                            >
                              {s.side}
                            </span>
                          </td>
                          <td className="whitespace-nowrap py-3 px-4">
                            {isActive ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                                <span className="size-1.5 rounded-full bg-amber-500 animate-pulse" />
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                                Completed
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-xs font-mono text-foreground">
                            {isActive || !s.hasResult ? "—" : s.repetitions}
                          </td>
                          <td className="py-3 px-4 text-xs font-mono text-foreground">
                            {isActive || !s.hasResult ? "—" : `${s.rom.toFixed(1)}°`}
                          </td>
                          <td className="py-3 px-4 text-xs font-mono font-bold text-foreground">
                            {!isActive && s.hasResult && s.score !== null ? `${s.score}%` : "—"}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // RENDER: SCREEN 3 — READY TO START / LIVE SESSION / SUMMARY
  // -------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-background font-sans flex flex-col">
      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

      {/* Header */}
      <header className="flex items-center justify-between border-b border-border/40 bg-card/50 px-6 py-4 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-4">
          <button
            type="button"
            disabled={sessionStatus === "active" || sessionStatus === "preparing" || sessionStatus === "finalizing"}
            onClick={() => {
              fullTeardown(false);
              setSelectedAssignment(null);
              setSessionStatus("idle");
              setFinalResult(null);
              if (selectedPatient) {
                loadPatientData(selectedPatient.id);
              }
            }}
            className="flex size-10 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shadow-sm disabled:opacity-40"
            title="Back to Assigned Exercises"
          >
            <ArrowLeft className="size-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-emerald-600 dark:text-emerald-400 tracking-tight flex items-center gap-2">
              <Activity className="size-5" />
              Patient Portal
            </h1>
            <p className="text-xs text-muted-foreground">
              {selectedPatient.name} • {selectedAssignment.exercise_name || selectedAssignment.exercise_id}
            </p>
          </div>
        </div>

        {sessionStatus === "active" && (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex flex-col items-end mr-2">
              <span className="text-[10px] text-muted-foreground font-semibold uppercase">Session ID</span>
              <span className="text-xs font-mono text-foreground font-bold">{sessionId}</span>
            </div>
            <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-400">
              <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
              LIVE
            </span>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="flex-1 p-6 flex flex-col items-center max-w-4xl mx-auto w-full gap-6">
        {/* Prescribed Assignment Summary Banner */}
        <div className="w-full rounded-2xl border border-border bg-card p-5 shadow-card space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground block">
                Prescribed Exercise
              </span>
              <h2 className="text-2xl font-bold text-foreground">
                {selectedAssignment.exercise_name || selectedAssignment.exercise_id}
              </h2>
            </div>

            <div className="flex items-center gap-2">
              {/* Prescribed Side — NON-EDITABLE badge */}
              <span
                className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold uppercase ${
                  selectedAssignment.side.toLowerCase() === "right"
                    ? "bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/30"
                    : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                }`}
              >
                {selectedAssignment.side} Side (Prescribed)
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-1 border-t border-border/60">
            <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
              <span className="text-[11px] font-medium text-muted-foreground block">Target ROM</span>
              <span className="text-base font-bold text-foreground">
                {selectedAssignment.target_rom !== null ? `${selectedAssignment.target_rom}°` : "Standard"}
              </span>
            </div>
            <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
              <span className="text-[11px] font-medium text-muted-foreground block">Target Repetitions</span>
              <span className="text-base font-bold text-foreground">
                {selectedAssignment.target_repetitions !== null ? selectedAssignment.target_repetitions : "Standard"}
              </span>
            </div>
            <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5 col-span-2 sm:col-span-1">
              <span className="text-[11px] font-medium text-muted-foreground block">Prescription</span>
              <span className="text-base font-bold text-foreground">
                {selectedAssignment.sessions_per_day}x / day
              </span>
            </div>
          </div>

          {selectedAssignment.notes && (
            <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/20 p-2.5 rounded-xl border border-border/40">
              <FileText className="size-3.5 shrink-0 mt-0.5" />
              <span>Therapist Instructions: "{selectedAssignment.notes}"</span>
            </div>
          )}
        </div>

        {/* WS / session error banner */}
        {wsError && (
          <div className="w-full flex items-center gap-3 bg-destructive/10 border border-destructive/30 rounded-xl px-4 py-3 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            <span>{wsError}</span>
          </div>
        )}

        {/* Camera + Live Stats row */}
        <div className="w-full flex flex-col lg:flex-row gap-6">
          {/* Camera Viewport */}
          <div className="relative flex-1 aspect-video rounded-3xl overflow-hidden border-2 border-border/50 bg-card shadow-2xl flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`absolute inset-0 w-full h-full object-cover transform -scale-x-100 transition-opacity duration-500 ${
                cameraStatus === "active" ? "opacity-100" : "opacity-0"
              }`}
            />

            {cameraStatus === "idle" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-muted/20 backdrop-blur-sm gap-4 text-muted-foreground z-10 p-4">
                <div className="p-5 rounded-full bg-background border border-border shadow-sm">
                  <CameraOff className="size-8 opacity-50" />
                </div>
                <p className="font-medium text-lg text-center">Camera Ready</p>
                <p className="text-xs opacity-70 max-w-sm text-center">
                  Position yourself so your full body is visible in good lighting. Click Start Session below to activate AI tracking.
                </p>
              </div>
            )}

            {cameraStatus === "loading" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md gap-4 z-10">
                <Loader2 className="size-10 text-emerald-500 animate-spin" />
                <p className="font-medium text-foreground">Accessing secure camera feed...</p>
                <p className="text-xs text-muted-foreground">Please allow camera permissions if prompted.</p>
              </div>
            )}

            {cameraStatus === "error" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-destructive/5 backdrop-blur-md gap-4 z-10 p-4">
                <div className="p-4 rounded-full bg-destructive/10 text-destructive border border-destructive/20">
                  <AlertCircle className="size-8" />
                </div>
                <p className="font-bold text-destructive text-lg">Camera Access Failed</p>
                <p className="text-xs text-muted-foreground max-w-md text-center">{cameraError}</p>
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
                    : "TRACKING ERROR"}
                </span>
              </div>
            )}

            {/* Live pose guidance banner */}
            {sessionStatus === "active" && cameraStatus === "active" && poseFeedback.code !== "VALID" && (
              <div
                id="pose-guidance-banner"
                className="absolute bottom-4 left-4 right-4 z-20 flex items-center gap-2.5 bg-background/90 backdrop-blur-md border border-amber-500/30 rounded-xl px-3.5 py-2 text-xs font-medium text-amber-300 shadow-lg"
              >
                <AlertCircle className="size-4 shrink-0 text-amber-400" />
                <span className="leading-snug">{poseFeedback.message}</span>
              </div>
            )}

            {/* Preparing overlay */}
            {sessionStatus === "preparing" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md gap-4 z-20">
                <Loader2 className="size-10 text-emerald-500 animate-spin" />
                <p className="font-medium text-foreground">Preparing rehabilitation session...</p>
                <p className="text-xs text-muted-foreground">Initializing camera and digital thread</p>
              </div>
            )}

            {/* Finalizing overlay */}
            {sessionStatus === "finalizing" && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md gap-4 z-20">
                <Loader2 className="size-10 text-emerald-500 animate-spin" />
                <p className="font-medium text-foreground">Finalising session...</p>
                <p className="text-xs text-muted-foreground">Committing authoritative result to digital thread</p>
              </div>
            )}
          </div>

          {/* Live stats panel */}
          {(sessionStatus === "active" || sessionStatus === "finalizing") && (
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
          <div className="w-full bg-card border border-border rounded-3xl p-6 shadow-lg space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="size-6 text-emerald-500" />
                <div>
                  <h3 className="text-xl font-bold text-foreground">Session Completed</h3>
                  {sessionCompletedAt && (
                    <p className="text-xs text-muted-foreground">
                      Completed on {formatDateTime(sessionCompletedAt)}
                    </p>
                  )}
                </div>
              </div>
              <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 uppercase">
                {selectedAssignment.exercise_name || selectedAssignment.exercise_id} ({selectedAssignment.side})
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <SummaryCard
                label="Repetitions"
                value={finalResult.repetitions !== null ? String(finalResult.repetitions) : "—"}
              />
              <SummaryCard
                label="Score"
                value={finalResult.performanceScore !== null ? `${finalResult.performanceScore.toFixed(1)}%` : "—"}
                valueClass={scoreColor}
              />
              <SummaryCard
                label="ROM Average"
                value={finalResult.romAverage !== null ? `${finalResult.romAverage.toFixed(1)}°` : "—"}
              />
              <SummaryCard
                label="ROM Range"
                value={
                  finalResult.romMin !== null && finalResult.romMax !== null
                    ? `${finalResult.romMin.toFixed(0)}° – ${finalResult.romMax.toFixed(0)}°`
                    : "—"
                }
              />
            </div>

            {finalResult.feedback ? (
              <p className="text-sm text-muted-foreground border-t border-border pt-3">{finalResult.feedback}</p>
            ) : (
              <p className="text-sm text-muted-foreground italic border-t border-border pt-3">No feedback recorded</p>
            )}

            <div className="flex flex-wrap items-center gap-4 pt-3 border-t border-border">
              <button
                type="button"
                onClick={() => {
                  setSessionStatus("idle");
                  setFinalResult(null);
                  setSessionId(null);
                }}
                className="text-sm font-semibold text-emerald-600 hover:text-emerald-500 transition-colors"
              >
                Perform another set
              </button>
              <button
                type="button"
                onClick={() => {
                  setSelectedAssignment(null);
                  setSessionStatus("idle");
                  setFinalResult(null);
                  setSessionId(null);
                  if (selectedPatient) {
                    loadPatientData(selectedPatient.id);
                  }
                }}
                className="text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors"
              >
                Back to Exercises
              </button>
              <button
                type="button"
                onClick={handleSwitchPatient}
                className="text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors sm:ml-auto"
              >
                Switch Patient
              </button>
            </div>
          </div>
        )}

        {/* Session Action Controls */}
        <div className="flex flex-wrap justify-center gap-4 w-full max-w-md">
          {sessionStatus === "idle" || sessionStatus === "completed" ? (
            <button
              onClick={handleStartSession}
              disabled={isActionLoading}
              id="btn-start-session"
              className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-8 py-4 font-bold text-white shadow-lg hover:bg-emerald-500 hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 cursor-pointer"
            >
              {isActionLoading ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Play className="size-5 fill-current" />
              )}
              Start Rehab Session
            </button>
          ) : sessionStatus === "error" ? (
            <button
              onClick={sessionId ? handleEndSession : handleStartSession}
              disabled={isActionLoading}
              id="btn-retry-session"
              className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-amber-600 px-8 py-4 font-bold text-white shadow-lg hover:bg-amber-500 hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 cursor-pointer"
            >
              {isActionLoading ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <RotateCcw className="size-5" />
              )}
              {sessionId ? "Retry Finalization" : "Retry Session"}
            </button>
          ) : (
            <button
              onClick={handleEndSession}
              disabled={isActionLoading || sessionStatus === "finalizing"}
              id="btn-end-session"
              className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-destructive px-8 py-4 font-bold text-white shadow-lg hover:bg-destructive/90 hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200 cursor-pointer"
            >
              {isActionLoading || sessionStatus === "finalizing" ? (
                <Loader2 className="size-5 animate-spin" />
              ) : (
                <Square className="size-5 fill-current" />
              )}
              {sessionStatus === "finalizing" ? "Finalizing..." : "End Session"}
            </button>
          )}
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Presentational sub-components
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
