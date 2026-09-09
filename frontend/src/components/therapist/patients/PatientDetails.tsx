import { Activity, CalendarDays, CheckCircle2, Clock, IdCard } from "lucide-react";
import type { Patient } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";

export function PatientDetails({ patient }: { patient: Patient }) {
  const hasActive = patient.activeSessions > 0;

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-foreground">Patient Profile</h2>
        {hasActive ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-600 dark:text-amber-400 border border-amber-500/30">
            <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
            Session Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
            <CheckCircle2 className="size-3.5 text-muted-foreground" />
            Completed / Idle
          </span>
        )}
      </div>

      <div className="mt-4 flex flex-col sm:flex-row gap-5">
        <div className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-secondary text-base font-bold text-secondary-foreground font-sans border border-border/40 shadow-sm">
          {patient.id}
        </div>

        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <h3 className="text-xl font-bold text-foreground tracking-tight">{patient.name}</h3>
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
              <IdCard className="size-3.5" /> ID: {patient.id}
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
            <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
              <p className="text-[11px] font-medium text-muted-foreground">Total Sessions</p>
              <p className="text-base font-bold text-foreground mt-0.5">{patient.sessionCount}</p>
            </div>
            <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
              <p className="text-[11px] font-medium text-muted-foreground">Active Sessions</p>
              <p className="text-base font-bold text-foreground mt-0.5">{patient.activeSessions}</p>
            </div>
            <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
              <p className="text-[11px] font-medium text-muted-foreground">Completed</p>
              <p className="text-base font-bold text-foreground mt-0.5">{patient.completedSessions}</p>
            </div>
            <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
              <p className="text-[11px] font-medium text-muted-foreground">Avg. Score</p>
              <p className="text-base font-bold text-foreground mt-0.5">
                {patient.avgPerformanceScore !== null ? `${patient.avgPerformanceScore}%` : "—"}
              </p>
            </div>
          </div>

          {patient.lastActive && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground pt-1">
              <Clock className="size-3.5" /> Last active: {formatDateTime(patient.lastActive)}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
