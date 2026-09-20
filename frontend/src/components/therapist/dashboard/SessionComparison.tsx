import { useEffect, useState } from "react";
import type { Session } from "@/types/rehab";
import { formatDate, formatDateTime, signed } from "@/lib/format";

const qualityRank = { Poor: 0, Fair: 1, Good: 2, Excellent: 3 } as const;

export function SessionComparison({ sessions }: { sessions: Session[] }) {
  const [aId, setAId] = useState<number>(sessions[0]?.id ?? 0);
  const [bId, setBId] = useState<number>(sessions[sessions.length - 1]?.id ?? 0);

  useEffect(() => {
    setAId(sessions[0]?.id ?? 0);
    setBId(sessions[sessions.length - 1]?.id ?? 0);
  }, [sessions]);

  const a = sessions.find((s) => s.id === aId);
  const b = sessions.find((s) => s.id === bId);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-foreground">Session Comparison</h2>
        <div className="flex flex-wrap gap-2">
          <SessionSelect sessions={sessions} value={aId} onChange={setAId} />
          <SessionSelect sessions={sessions} value={bId} onChange={setBId} />
        </div>
      </div>

      {a && b ? (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Metric</th>
                <th className="py-2 pr-3 font-medium">Session {a.id}</th>
                <th className="py-2 pr-3 font-medium">Session {b.id}</th>
                <th className="py-2 font-medium">Improvement</th>
              </tr>
            </thead>
            <tbody>
              <Row label="Exercise" a={a.exercise} b={b.exercise} />
              <Row
                label="Repetitions"
                a={a.repetitions}
                b={b.repetitions}
                delta={signed(b.repetitions - a.repetitions)}
                positive={b.repetitions >= a.repetitions}
              />
              <Row
                label="ROM"
                a={`${a.rom.toFixed(1)}°`}
                b={`${b.rom.toFixed(1)}°`}
                delta={signed(b.rom - a.rom, "°")}
                positive={b.rom >= a.rom}
              />
              <Row
                label="Movement Quality"
                a={a.quality}
                b={b.quality}
                delta={
                  qualityRank[b.quality] === qualityRank[a.quality]
                    ? "—"
                    : qualityRank[b.quality] > qualityRank[a.quality]
                      ? "Improved"
                      : "Declined"
                }
                positive={qualityRank[b.quality] >= qualityRank[a.quality]}
              />
              <Row
                label="Performance Score"
                a={`${a.score}%`}
                b={`${b.score}%`}
                delta={signed(b.score - a.score, "%")}
                positive={b.score >= a.score}
              />
              <Row label="Session Date" a={formatDateTime(a.dateTime)} b={formatDateTime(b.dateTime)} />
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">Select two sessions to compare.</p>
      )}
    </section>
  );
}

function SessionSelect({
  sessions,
  value,
  onChange,
}: {
  sessions: Session[];
  value: number;
  onChange: (id: number) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-ring transition-colors cursor-pointer"
    >
      {sessions.map((s) => (
        <option key={s.id} value={s.id}>
          Session {s.id} ({formatDate(s.dateTime)})
        </option>
      ))}
    </select>
  );
}

function Row({
  label,
  a,
  b,
  delta,
  positive,
}: {
  label: string;
  a: string | number;
  b: string | number;
  delta?: string;
  positive?: boolean;
}) {
  return (
    <tr className="border-b border-border/40 last:border-0 hover:bg-muted/30 transition-colors">
      <td className="py-3 pr-3 font-medium text-foreground">{label}</td>
      <td className="py-3 pr-3 text-muted-foreground">{a}</td>
      <td className="py-3 pr-3 text-foreground">{b}</td>
      <td
        className={
          delta && delta !== "—" && delta !== "Declined"
            ? "py-3 font-semibold text-success-foreground"
            : delta === "Declined"
              ? "py-3 font-semibold text-destructive"
              : "py-3 text-muted-foreground"
        }
      >
        {delta ?? "—"}
      </td>
    </tr>
  );
}
