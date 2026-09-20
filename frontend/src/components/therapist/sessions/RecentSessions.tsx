import type { Session } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";
import { StatusBadge } from "../../ui/StatusBadge";

export function RecentSessions({ sessions }: { sessions: Session[] }) {
  const rows = [...sessions].reverse();

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-foreground">Recent Sessions</h2>
        <button type="button" className="text-sm font-semibold text-primary hover:underline transition-colors btn-interactive">
          View All Sessions
        </button>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Session</th>
              <th className="py-2 pr-3 font-medium">Date &amp; Time</th>
              <th className="py-2 pr-3 font-medium">Exercise</th>
              <th className="py-2 pr-3 font-medium">Reps</th>
              <th className="py-2 pr-3 font-medium">ROM (°)</th>
              <th className="py-2 pr-3 font-medium">Quality</th>
              <th className="py-2 font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} className="border-b border-border/40 last:border-0 hover:bg-muted/30 transition-colors">
                <td className="py-3 pr-3 font-semibold text-foreground font-sans">{s.id}</td>
                <td className="whitespace-nowrap py-3 pr-3 text-muted-foreground font-sans">
                  {formatDateTime(s.dateTime)}
                </td>
                <td className="whitespace-nowrap py-3 pr-3 text-foreground">{s.exercise}</td>
                <td className="py-3 pr-3 text-foreground font-sans">{s.repetitions}</td>
                <td className="py-3 pr-3 text-foreground font-sans">{s.rom.toFixed(1)}</td>
                <td className="py-3 pr-3">
                  <StatusBadge value={s.quality} />
                </td>
                <td className="py-3 font-semibold text-foreground font-sans">{s.score}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
