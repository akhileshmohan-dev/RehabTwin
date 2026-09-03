import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Camera,
  CameraOff,
  Play,
  Square,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { startSession, endSession } from "@/data/rehabService";

export const Route = createFileRoute("/patient")({
  head: () => ({
    meta: [
      { title: "RehabTwin — Patient Portal" },
      {
        name: "description",
        content: "Patient portal for live rehabilitation exercises and camera tracking.",
      },
    ],
  }),
  component: PatientPortal,
});

type CameraStatus = "idle" | "loading" | "active" | "error";
type SessionStatus = "idle" | "active";

function PatientPortal() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("idle");
  const [cameraError, setCameraError] = useState<string>("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);

  // Stop camera tracks cleanly
  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraStatus("idle");
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stream]);

  const handleStartSession = async () => {
    if (isActionLoading) return;
    setIsActionLoading(true);
    setCameraError("");
    setCameraStatus("loading");

    try {
      // 1. Request camera BEFORE creating the backend session
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
      });

      // 2. Camera succeeded, set up local state
      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
      setCameraStatus("active");

      // 3. Call backend to start session
      try {
        const response = await startSession("P001", "elbow_flexion");
        setSessionId(response.session_id);
        setSessionStatus("active");
      } catch (backendErr: any) {
        // If backend fails, stop the camera we just started
        stopCamera();
        setCameraStatus("error");
        setCameraError(`Backend Error: ${backendErr.message}`);
      }
    } catch (cameraErr: any) {
      console.error("Camera access denied or failed:", cameraErr);
      setCameraStatus("error");
      setCameraError("Camera access denied or device not found. Please allow camera permissions.");
      // Do NOT create backend session
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleEndSession = async () => {
    if (isActionLoading || !sessionId) return;
    setIsActionLoading(true);

    try {
      // Attempt backend endSession()
      await endSession(sessionId);
    } catch (err) {
      console.error("Failed to end session on backend:", err);
    } finally {
      // ALWAYS stop local MediaStream even if backend request fails
      stopCamera();
      setSessionStatus("idle");
      setSessionId(null);
      setIsActionLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background font-sans flex flex-col">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border/40 bg-card/50 px-6 py-4 backdrop-blur-md sticky top-0 z-10">
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

      {/* Main Content Area */}
      <main className="flex-1 p-6 flex flex-col items-center justify-center max-w-6xl mx-auto w-full gap-8">
        
        {/* Title & Description */}
        <div className="w-full text-center space-y-2">
          <h2 className="text-2xl font-bold text-foreground">Elbow Flexion Exercise</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Position yourself clearly in the camera frame. Ensure your full arm is visible before starting the exercise. Follow the standard clinical motion.
          </p>
        </div>

        {/* Camera Container */}
        <div className="relative w-full max-w-4xl aspect-video rounded-3xl overflow-hidden border-2 border-border/50 bg-card shadow-2xl flex items-center justify-center group transition-all duration-500">
          
          {/* Active Camera Feed */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className={`absolute inset-0 w-full h-full object-cover transform -scale-x-100 transition-opacity duration-500 ${cameraStatus === "active" ? "opacity-100" : "opacity-0"}`}
          />

          {/* Idle State Overlay */}
          {cameraStatus === "idle" && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-muted/20 backdrop-blur-sm gap-4 text-muted-foreground z-10 animate-fade-in">
              <div className="p-5 rounded-full bg-background border border-border shadow-sm">
                <CameraOff className="size-8 opacity-50" />
              </div>
              <p className="font-medium text-lg">Camera is inactive</p>
              <p className="text-sm opacity-70 max-w-sm text-center">Click Start Session below to enable your camera and begin rehabilitation tracking.</p>
            </div>
          )}

          {/* Loading State Overlay */}
          {cameraStatus === "loading" && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/80 backdrop-blur-md gap-4 z-10 animate-fade-in">
              <Loader2 className="size-10 text-emerald-500 animate-spin" />
              <p className="font-medium text-foreground">Accessing secure camera feed...</p>
              <p className="text-sm text-muted-foreground">Please allow camera permissions if prompted.</p>
            </div>
          )}

          {/* Error State Overlay */}
          {cameraStatus === "error" && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-destructive/5 backdrop-blur-md gap-4 z-10 animate-fade-in">
              <div className="p-4 rounded-full bg-destructive/10 text-destructive border border-destructive/20">
                <AlertCircle className="size-8" />
              </div>
              <p className="font-bold text-destructive text-lg">Camera Access Failed</p>
              <p className="text-sm text-muted-foreground max-w-md text-center">{cameraError}</p>
            </div>
          )}
          
          {/* Active Recording Indicator (Top Left) */}
          {cameraStatus === "active" && (
            <div className="absolute top-4 left-4 flex items-center gap-2 bg-black/50 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 z-20">
              <span className="size-2.5 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs font-medium tracking-wide text-white drop-shadow-sm">REC</span>
            </div>
          )}
        </div>

        {/* Controls Panel */}
        <div className="flex flex-wrap justify-center gap-4 w-full max-w-md">
          {sessionStatus === "idle" ? (
            <button
              onClick={handleStartSession}
              disabled={isActionLoading}
              className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-emerald-600 px-8 py-4 font-bold text-white shadow-lg hover:bg-emerald-500 hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200"
            >
              {isActionLoading ? <Loader2 className="size-5 animate-spin" /> : <Play className="size-5 fill-current" />}
              Start Rehab Session
            </button>
          ) : (
            <button
              onClick={handleEndSession}
              disabled={isActionLoading}
              className="flex-1 flex items-center justify-center gap-2 rounded-2xl bg-destructive px-8 py-4 font-bold text-white shadow-lg hover:bg-destructive/90 hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none transition-all duration-200"
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
