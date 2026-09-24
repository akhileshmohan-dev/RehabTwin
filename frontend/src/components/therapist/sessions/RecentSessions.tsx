import type { Session } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";

export function RecentSessions({ sessions }: { sessions: Session[] }) {
  // Explicit newest-first: take first 5 sessions directly
  const rows = sessions.slice(0, 5);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-foreground">Recent Sessions</h2>
        <span className="text-xs text-muted-foreground font-medium">
          Showing {rows.length} of {sessions.length}
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Session ID</th>
              <th className="py-2 pr-3 font-medium">Date &amp; Time</th>
              <th className="py-2 pr-3 font-medium">Exercise</th>
              <th className="py-2 pr-3 font-medium">Side</th>
              <th className="py-2 pr-3 font-medium">Status</th>
              <th className="py-2 pr-3 font-medium">Reps</th>
              <th className="py-2 pr-3 font-medium">ROM</th>
              <th className="py-2 font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const isActive = s.status === "ACTIVE";
              const isCompleted = s.status === "COMPLETED";
              return (
                <tr key={s.rawSessionId || s.id} className="border-b border-border/40 last:border-0 hover:bg-muted/30 transition-colors">
                  <td className="py-3 pr-3 font-semibold text-foreground font-sans text-xs">
                    {s.rawSessionId ? s.rawSessionId : `S-${s.id}`}
                  </td>
                  <td className="whitespace-nowrap py-3 pr-3 text-muted-foreground font-sans text-xs">
                    {formatDateTime(s.dateTime)}
                  </td>
                  <td className="whitespace-nowrap py-3 pr-3 text-foreground font-medium">{s.exercise}</td>
                  <td className="whitespace-nowrap py-3 pr-3 text-foreground">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                        s.side.toLowerCase() === "right"
                          ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                          : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                      }`}
                    >
                      {s.side}
                    </span>
                  </td>
                  <td className="whitespace-nowrap py-3 pr-3">
                    {isActive ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400 border border-amber-500/30">
                        <span className="size-1.5 rounded-full bg-amber-500 animate-pulse" />
                        Active
                      </span>
                    ) : isCompleted ? (
                      <span className="inline-flex items-center rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                        Completed
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {s.status}
                      </span>
                    )}
                  </td>
                  <td className="py-3 pr-3 text-foreground font-sans text-xs">
                    {isActive || !s.hasResult ? "—" : s.repetitions}
                  </td>
                  <td className="py-3 pr-3 text-foreground font-sans text-xs">
                    {isActive || !s.hasResult ? "—" : `${s.rom.toFixed(1)}°`}
                  </td>
                  <td className="py-3 font-semibold text-foreground font-sans text-xs">
                    {!isActive && s.hasResult && s.score !== null ? `${s.score}%` : "—"}
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-xs text-muted-foreground">
                  No sessions recorded for this patient.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
