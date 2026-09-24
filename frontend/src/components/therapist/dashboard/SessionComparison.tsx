import { useEffect, useMemo, useState } from "react";
import type { Session } from "@/types/rehab";
import { formatDateTime, signed } from "@/lib/format";

export function SessionComparison({ sessions }: { sessions: Session[] }) {
  // Only completed sessions with valid persisted results are comparable
  const eligibleSessions = useMemo(() => {
    return sessions.filter((s) => s.status === "COMPLETED" && s.hasResult && s.score !== null);
  }, [sessions]);

  // Group by exact (exercise, side) combinations
  const seriesMap = useMemo(() => {
    const map = new Map<string, { label: string; exercise: string; side: string; sessions: Session[] }>();
    for (const s of eligibleSessions) {
      const key = `${s.exerciseId || s.exercise}|${s.side}`;
      if (!map.has(key)) {
        map.set(key, {
          label: `${s.exercise} (${s.side.charAt(0).toUpperCase() + s.side.slice(1)})`,
          exercise: s.exercise,
          side: s.side,
          sessions: [],
        });
      }
      map.get(key)!.sessions.push(s);
    }
    return map;
  }, [eligibleSessions]);

  // Filter groups that have at least 2 sessions available to compare
  const comparableGroups = useMemo(() => {
    return Array.from(seriesMap.entries())
      .filter(([_, group]) => group.sessions.length >= 2)
      .map(([key, group]) => ({
        key,
        label: group.label,
        sessions: group.sessions,
      }));
  }, [seriesMap]);

  const [selectedGroupKey, setSelectedGroupKey] = useState<string>("");
  const [aSessionId, setASessionId] = useState<string>("");
  const [bSessionId, setBSessionId] = useState<string>("");

  useEffect(() => {
    if (comparableGroups.length > 0) {
      if (!comparableGroups.some((g) => g.key === selectedGroupKey)) {
        setSelectedGroupKey(comparableGroups[0].key);
      }
    } else {
      setSelectedGroupKey("");
    }
  }, [comparableGroups, selectedGroupKey]);

  const currentGroup = useMemo(() => {
    return comparableGroups.find((g) => g.key === selectedGroupKey);
  }, [comparableGroups, selectedGroupKey]);

  useEffect(() => {
    if (currentGroup && currentGroup.sessions.length >= 2) {
      const sorted = [...currentGroup.sessions].sort(
        (x, y) => new Date(x.dateTime).getTime() - new Date(y.dateTime).getTime()
      );
      // Default: oldest as Session A, newest as Session B
      setASessionId(sorted[0].rawSessionId || String(sorted[0].id));
      setBSessionId(sorted[sorted.length - 1].rawSessionId || String(sorted[sorted.length - 1].id));
    } else {
      setASessionId("");
      setBSessionId("");
    }
  }, [currentGroup]);

  const sessionA = currentGroup?.sessions.find((s) => (s.rawSessionId || String(s.id)) === aSessionId);
  const sessionB = currentGroup?.sessions.find((s) => (s.rawSessionId || String(s.id)) === bSessionId);

  // Chronological identification: older = baseline, newer = follow-up
  const comparison = useMemo(() => {
    if (!sessionA || !sessionB) return null;
    const timeA = new Date(sessionA.dateTime).getTime();
    const timeB = new Date(sessionB.dateTime).getTime();

    const [baseline, followup] = timeA <= timeB ? [sessionA, sessionB] : [sessionB, sessionA];

    const repDelta = followup.repetitions - baseline.repetitions;
    const romDelta = followup.rom - baseline.rom;
    const scoreDelta = (followup.score ?? 0) - (baseline.score ?? 0);

    return {
      baseline,
      followup,
      repDelta,
      romDelta,
      scoreDelta,
    };
  }, [sessionA, sessionB]);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-foreground">Session Comparison</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Strictly Same Exercise &amp; Side</p>
        </div>

        {comparableGroups.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {comparableGroups.length > 1 && (
              <select
                value={selectedGroupKey}
                onChange={(e) => setSelectedGroupKey(e.target.value)}
                className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground outline-none focus:border-primary cursor-pointer shadow-sm"
              >
                {comparableGroups.map((g) => (
                  <option key={g.key} value={g.key}>
                    {g.label}
                  </option>
                ))}
              </select>
            )}

            {currentGroup && (
              <div className="flex items-center gap-1.5">
                <select
                  value={aSessionId}
                  onChange={(e) => setASessionId(e.target.value)}
                  className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none focus:border-primary cursor-pointer shadow-sm"
                >
                  {currentGroup.sessions.map((s) => (
                    <option key={s.rawSessionId || s.id} value={s.rawSessionId || String(s.id)}>
                      {s.rawSessionId ? s.rawSessionId.slice(-7) : `S-${s.id}`} ({formatDateTime(s.dateTime).slice(0, 10)})
                    </option>
                  ))}
                </select>

                <span className="text-xs text-muted-foreground font-semibold">vs</span>

                <select
                  value={bSessionId}
                  onChange={(e) => setBSessionId(e.target.value)}
                  className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none focus:border-primary cursor-pointer shadow-sm"
                >
                  {currentGroup.sessions.map((s) => (
                    <option key={s.rawSessionId || s.id} value={s.rawSessionId || String(s.id)}>
                      {s.rawSessionId ? s.rawSessionId.slice(-7) : `S-${s.id}`} ({formatDateTime(s.dateTime).slice(0, 10)})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}
      </div>

      {comparison && currentGroup ? (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-medium text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Metric</th>
                <th className="py-2 pr-3 font-medium">
                  Baseline ({comparison.baseline.rawSessionId ? comparison.baseline.rawSessionId.slice(-7) : `S-${comparison.baseline.id}`})
                </th>
                <th className="py-2 pr-3 font-medium">
                  Follow-up ({comparison.followup.rawSessionId ? comparison.followup.rawSessionId.slice(-7) : `S-${comparison.followup.id}`})
                </th>
                <th className="py-2 font-medium">Chronological Delta</th>
              </tr>
            </thead>
            <tbody>
              <Row
                label="Exercise & Side"
                a={currentGroup.label}
                b={currentGroup.label}
                delta="Identical"
              />
              <Row
                label="Repetitions"
                a={comparison.baseline.repetitions}
                b={comparison.followup.repetitions}
                delta={signed(comparison.repDelta)}
                positive={comparison.repDelta >= 0}
              />
              <Row
                label="ROM Excursion"
                a={`${comparison.baseline.rom.toFixed(1)}°`}
                b={`${comparison.followup.rom.toFixed(1)}°`}
                delta={signed(comparison.romDelta, "°")}
                positive={comparison.romDelta >= 0}
              />
              <Row
                label="Performance Score"
                a={`${comparison.baseline.score ?? 0}%`}
                b={`${comparison.followup.score ?? 0}%`}
                delta={signed(comparison.scoreDelta, "%")}
                positive={comparison.scoreDelta >= 0}
              />
              <Row
                label="Date & Time"
                a={formatDateTime(comparison.baseline.dateTime)}
                b={formatDateTime(comparison.followup.dateTime)}
              />
            </tbody>
          </table>
        </div>
      ) : (
        <div className="py-10 text-center text-xs text-muted-foreground leading-relaxed">
          At least two completed sessions of the exact same exercise and side are required for clinical comparison.
        </div>
      )}
    </section>
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
      <td className="py-3 pr-3 font-medium text-foreground text-xs">{label}</td>
      <td className="py-3 pr-3 text-muted-foreground text-xs font-sans">{a}</td>
      <td className="py-3 pr-3 text-foreground text-xs font-sans">{b}</td>
      <td
        className={
          delta && delta !== "—" && delta !== "Identical"
            ? positive
              ? "py-3 font-semibold text-emerald-600 dark:text-emerald-400 text-xs font-sans"
              : "py-3 font-semibold text-destructive text-xs font-sans"
            : "py-3 text-muted-foreground text-xs font-sans"
        }
      >
        {delta ?? "—"}
      </td>
    </tr>
  );
}
