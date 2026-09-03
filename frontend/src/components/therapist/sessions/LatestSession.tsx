import { Activity, Play, Square } from "lucide-react";
import type { Session } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";

interface LatestSessionProps {
  session?: (Session & { rawSessionId?: string; status?: string }) | undefined;
  onStartSession?: () => void;
  onEndSession?: (sessionId: string) => void;
  isActionLoading?: boolean;
}

export function LatestSession({
  session,
  onStartSession,
  onEndSession,
  isActionLoading,
}: LatestSessionProps) {
  if (!session) {
    return (
      <section className="rounded-2xl border border-border bg-card p-5 text-sm text-muted-foreground shadow-card card-interactive flex items-center justify-between">
        <span>No sessions recorded yet.</span>
        {onStartSession && (
          <button
            type="button"
            onClick={onStartSession}
            disabled={isActionLoading}
            className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm btn-interactive disabled:opacity-50 cursor-pointer"
          >
            <Play className="size-3.5 fill-current" />
            <span>Start Session</span>
          </button>
        )}
      </section>
    );
  }

  const circumference = 2 * Math.PI * 26;
  const offset = circumference * (1 - session.score / 100);
  const isActive = session.status === "ACTIVE";

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-bold text-foreground">Latest Session</h2>
          {isActive && (
            <span className="rounded-full bg-success/20 px-2.5 py-0.5 text-[10px] font-bold text-success-foreground animate-pulse">
              ACTIVE
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <p className="text-sm text-muted-foreground font-medium font-sans">
            {formatDateTime(session.dateTime)}
          </p>
          {isActive && session.rawSessionId && onEndSession ? (
            <button
              type="button"
              onClick={() => onEndSession(session.rawSessionId!)}
              disabled={isActionLoading}
              className="flex items-center gap-1.5 rounded-xl bg-destructive px-3 py-1.5 text-xs font-semibold text-destructive-foreground hover:bg-destructive/90 transition-colors shadow-sm btn-interactive disabled:opacity-50 cursor-pointer"
            >
              <Square className="size-3.5 fill-current" />
              <span>End Session</span>
            </button>
          ) : onStartSession ? (
            <button
              type="button"
              onClick={onStartSession}
              disabled={isActionLoading}
              className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm btn-interactive disabled:opacity-50 cursor-pointer"
            >
              <Play className="size-3.5 fill-current" />
              <span>Start Session</span>
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-4">
        <div className="flex size-12 items-center justify-center rounded-xl bg-primary-soft transition-transform duration-300 hover:scale-105">
          <Activity className="size-5 text-primary" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium">Exercise</p>
          <p className="text-lg font-semibold text-foreground tracking-tight">{session.exercise}</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-4 border-t border-border/40 pt-5 sm:grid-cols-4">
        <Stat label="Repetitions" value={String(session.repetitions)} />
        <Stat label="ROM" value={`${session.rom.toFixed(1)}°`} />
        <Stat label="Movement Quality" value={session.quality} tone />
        <div className="flex flex-col items-center gap-1">
          <p className="text-xs text-muted-foreground font-medium mb-1">Performance Score</p>
          <div className="relative size-16">
            <svg viewBox="0 0 60 60" className="size-16 -rotate-90">
              <circle cx="30" cy="30" r="26" className="fill-none stroke-muted" strokeWidth="7" />
              <circle
                cx="30"
                cy="30"
                r="26"
                className="fill-none stroke-primary transition-[stroke-dashoffset] duration-1000 ease-out"
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={offset}
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-foreground font-sans">
              {session.score}%
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 text-center">
      <p className="text-xs text-muted-foreground font-medium">{label}</p>
      <p
        className={
          tone ? "text-lg font-bold text-success-foreground" : "text-lg font-bold text-foreground font-sans"
        }
      >
        {value}
      </p>
    </div>
  );
}
