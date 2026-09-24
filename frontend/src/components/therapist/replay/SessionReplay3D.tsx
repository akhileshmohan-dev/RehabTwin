/**
 * 3D session replay wrapper.
 *
 * Owns playback state/clock and renders the three.js canvas lazily so that
 * three.js is never evaluated during SSR (the canvas mounts only after the
 * component has entered the browser).
 */
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Component, type ReactNode } from "react";
import { AlertCircle, Loader2, Pause, Play, Repeat } from "lucide-react";

import type { SessionFrame } from "@/types/rehab";

const ReplayCanvas = lazy(() => import("./ReplayCanvas"));

export interface SessionReplay3DProps {
  frames: SessionFrame[];
  exercise: string;
  side: string;
  sessionId?: string;
  onClose?: () => void;
}

function formatTime(ms: number): string {
  const total = Math.max(0, ms) / 1000;
  const minutes = Math.floor(total / 60);
  const seconds = total - minutes * 60;
  return `${minutes}:${seconds.toFixed(1).padStart(4, "0")}`;
}

class ReplayErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  override state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  override componentDidCatch(error: unknown) {
    console.error("3D replay failed to render", error);
  }

  override render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-2 bg-muted/20 text-center p-6">
          <AlertCircle className="size-6 text-destructive" />
          <p className="text-sm font-semibold text-foreground">3D model could not be loaded</p>
          <p className="text-xs text-muted-foreground">
            Check that /models/Character_Model.glb is available.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function SessionReplay3D({
  frames,
  exercise,
  side,
  sessionId,
  onClose,
}: SessionReplay3DProps) {
  const [mounted, setMounted] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [loop, setLoop] = useState(true);
  const [timeMs, setTimeMs] = useState(0);

  const timeRef = useRef(0);
  const lastTsRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const durationMs = frames.length > 0 ? frames[frames.length - 1]?.t_ms ?? 0 : 0;

  // Playback clock — advances timeRef without re-rendering the canvas.
  useEffect(() => {
    if (!playing || durationMs <= 0) {
      lastTsRef.current = null;
      return;
    }
    const tick = (ts: number) => {
      if (lastTsRef.current !== null) {
        const deltaMs = (ts - lastTsRef.current) * speed;
        let next = timeRef.current + deltaMs;
        if (next >= durationMs) {
          if (loop) {
            next = next % durationMs;
          } else {
            next = durationMs;
            setPlaying(false);
          }
        }
        timeRef.current = next;
        setTimeMs(next);
      }
      lastTsRef.current = ts;
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      lastTsRef.current = null;
    };
  }, [playing, speed, loop, durationMs]);

  const seek = (value: number) => {
    timeRef.current = value;
    setTimeMs(value);
  };

  return (
    <div className="flex w-full flex-col gap-3 rounded-2xl border border-border bg-card p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-foreground">3D Movement Replay</h3>
          <p className="text-xs text-muted-foreground">
            {exercise} · {side} side{typeof frames.length === "number" ? ` · ${frames.length} frames` : ""}
            {sessionId ? ` · ${sessionId}` : ""}
          </p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            Close
          </button>
        )}
      </div>

      <div className="relative h-[380px] w-full overflow-hidden rounded-xl border border-border bg-[#0f1216]">
        {frames.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center p-6">
            <AlertCircle className="size-6 text-amber-500" />
            <p className="text-sm font-semibold text-foreground">No frames recorded for this session</p>
            <p className="text-xs text-muted-foreground">
              Telemetry was not captured, so there is nothing to replay.
            </p>
          </div>
        ) : !mounted ? (
          <div className="flex h-full items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <span className="text-xs">Preparing 3D viewer…</span>
          </div>
        ) : (
          <ReplayErrorBoundary>
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center gap-2 text-muted-foreground">
                  <Loader2 className="size-5 animate-spin" />
                  <span className="text-xs">Loading character model…</span>
                </div>
              }
            >
              <ReplayCanvas frames={frames} side={side} timeRef={timeRef} />
            </Suspense>
          </ReplayErrorBoundary>
        )}
      </div>

      {/* Playback controls */}
      <div className="flex flex-col gap-2">
        <input
          type="range"
          min={0}
          max={Math.max(1, durationMs)}
          step={10}
          value={timeMs}
          onChange={(event) => seek(Number(event.target.value))}
          className="w-full accent-emerald-600"
          aria-label="Replay scrubber"
        />
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setPlaying((value) => !value)}
            disabled={frames.length === 0}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-50 transition-colors"
          >
            {playing ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
            {playing ? "Pause" : "Play"}
          </button>

          {[0.5, 1, 2].map((rate) => (
            <button
              key={rate}
              type="button"
              onClick={() => setSpeed(rate)}
              className={`rounded-lg border px-2.5 py-1.5 text-xs font-bold transition-colors ${
                speed === rate
                  ? "border-emerald-600 bg-emerald-600/15 text-emerald-600 dark:text-emerald-400"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {rate}×
            </button>
          ))}

          <button
            type="button"
            onClick={() => setLoop((value) => !value)}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-bold transition-colors ${
              loop
                ? "border-emerald-600 bg-emerald-600/15 text-emerald-600 dark:text-emerald-400"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            <Repeat className="size-3.5" />
            Loop
          </button>

          <span className="ml-auto text-xs font-semibold tabular-nums text-muted-foreground">
            {formatTime(timeMs)} / {formatTime(durationMs)}
          </span>
        </div>
      </div>
    </div>
  );
}
