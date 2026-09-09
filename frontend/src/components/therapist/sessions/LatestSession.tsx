import { Activity, CheckCircle2 } from "lucide-react";
import type { Session } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";

interface LatestSessionProps {
  session?: Session | undefined;
}

export function LatestSession({ session }: LatestSessionProps) {
  if (!session) {
    return (
      <section className="rounded-2xl border border-border bg-card p-6 text-sm text-muted-foreground shadow-card card-interactive text-center">
        No sessions recorded for this patient.
      </section>
    );
  }

  const isActive = session.status === "ACTIVE";
  const isCompleted = session.status === "COMPLETED";
  const hasResult = Boolean(session.hasResult && !isActive);

  let repetitionsDisplay = "—";
  let romDisplay = "—";
  let qualityDisplay = "—";
  let scoreDisplay = "—";

  if (isActive) {
    repetitionsDisplay = "In progress...";
    romDisplay = "In progress...";
    qualityDisplay = "In progress...";
    scoreDisplay = "—";
  } else if (hasResult) {
    repetitionsDisplay = String(session.repetitions);
    romDisplay = `${session.rom.toFixed(1)}°`;
    qualityDisplay = session.quality || "—";
    scoreDisplay = session.score !== null ? `${session.score}%` : "—";
  } else {
    repetitionsDisplay = "—";
    romDisplay = "—";
    qualityDisplay = "—";
    scoreDisplay = "—";
  }

  const scoreValue = hasResult && session.score !== null ? session.score : 0;
  const circumference = 2 * Math.PI * 26;
  const offset = circumference * (1 - Math.min(100, Math.max(0, scoreValue)) / 100);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <h2 className="text-lg font-bold text-foreground">Latest Session</h2>
          {isActive ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400 border border-amber-500/30">
              <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
              Live / In Progress
            </span>
          ) : isCompleted ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="size-3.5" />
              Completed
            </span>
          ) : (
            <span className="inline-flex items-center rounded-full bg-muted/70 px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              {session.status}
            </span>
          )}
        </div>

        <p className="text-xs text-muted-foreground font-medium font-sans">
          Started: {formatDateTime(session.dateTime)}
        </p>
      </div>

      <div className="mt-4 flex items-center gap-4">
        <div className="flex size-12 items-center justify-center rounded-xl bg-primary-soft transition-transform duration-300 hover:scale-105">
          <Activity className="size-5 text-primary" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium">Exercise</p>
          <div className="flex items-center gap-2">
            <p className="text-lg font-semibold text-foreground tracking-tight">{session.exercise}</p>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold uppercase ${
                session.side.toLowerCase() === "right"
                  ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                  : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
              }`}
            >
              {session.side}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-4 border-t border-border/40 pt-5 sm:grid-cols-4">
        <Stat
          label="Repetitions"
          value={repetitionsDisplay}
        />
        <Stat
          label="ROM Excursion"
          value={romDisplay}
        />
        <Stat
          label="Movement Quality"
          value={qualityDisplay}
          tone={hasResult && Boolean(session.quality)}
        />
        <div className="flex flex-col items-center gap-1">
          <p className="text-xs text-muted-foreground font-medium mb-1">Performance Score</p>
          <div className="relative size-16">
            <svg viewBox="0 0 60 60" className="size-16 -rotate-90">
              <circle cx="30" cy="30" r="26" className="fill-none stroke-muted" strokeWidth="7" />
              {hasResult && session.score !== null && (
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
              )}
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-foreground font-sans">
              {scoreDisplay}
            </span>
          </div>
        </div>
      </div>

      {hasResult && session.feedback && (
        <div className="mt-4 rounded-xl bg-muted/30 border border-border/40 px-3.5 py-2 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Clinical Feedback: </span>
          {session.feedback}
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 text-center">
      <p className="text-xs text-muted-foreground font-medium">{label}</p>
      <p
        className={
          tone ? "text-base font-bold text-success-foreground" : "text-base font-bold text-foreground font-sans"
        }
      >
        {value}
      </p>
    </div>
  );
}
