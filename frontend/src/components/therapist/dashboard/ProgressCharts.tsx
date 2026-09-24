import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Session } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";

interface SeriesOption {
  key: string;
  label: string;
  exercise: string;
  side: "left" | "right";
}

export function ProgressCharts({ sessions }: { sessions: Session[] }) {
  // Only completed sessions with persisted results enter progress charts
  const eligibleSessions = useMemo(() => {
    return sessions.filter((s) => s.status === "COMPLETED" && s.hasResult && s.score !== null);
  }, [sessions]);

  // Extract unique (exercise, side) combinations available
  const availableSeries = useMemo(() => {
    const map = new Map<string, SeriesOption>();
    for (const s of eligibleSessions) {
      const key = `${s.exerciseId || s.exercise}|${s.side}`;
      if (!map.has(key)) {
        map.set(key, {
          key,
          exercise: s.exercise,
          side: s.side,
          label: `${s.exercise} (${s.side.charAt(0).toUpperCase() + s.side.slice(1)})`,
        });
      }
    }
    return Array.from(map.values());
  }, [eligibleSessions]);

  const [selectedKey, setSelectedKey] = useState<string>("");

  useEffect(() => {
    if (availableSeries.length > 0) {
      // If current selection is invalid, default to the first available series
      if (!availableSeries.some((opt) => opt.key === selectedKey)) {
        setSelectedKey(availableSeries[0].key);
      }
    } else {
      setSelectedKey("");
    }
  }, [availableSeries, selectedKey]);

  // Filter sessions matching selected exercise + side
  const seriesData = useMemo(() => {
    if (!selectedKey) return [];
    const matching = eligibleSessions.filter((s) => `${s.exerciseId || s.exercise}|${s.side}` === selectedKey);
    // Chronological ordering: oldest first along X-axis
    return [...matching]
      .sort((a, b) => new Date(a.dateTime).getTime() - new Date(b.dateTime).getTime())
      .map((s, idx) => ({
        name: `S${idx + 1}`,
        sessionId: s.rawSessionId || `S-${s.id}`,
        dateTime: formatDateTime(s.dateTime),
        rom: s.rom,
        score: s.score ?? 0,
      }));
  }, [eligibleSessions, selectedKey]);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-foreground">Progress Trends</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Isolated by Exercise and Side</p>
        </div>

        {availableSeries.length > 1 && (
          <select
            value={selectedKey}
            onChange={(e) => setSelectedKey(e.target.value)}
            className="rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground outline-none focus:border-primary cursor-pointer shadow-sm"
          >
            {availableSeries.map((opt) => (
              <option key={opt.key} value={opt.key}>
                {opt.label}
              </option>
            ))}
          </select>
        )}
      </div>

      {availableSeries.length > 0 && selectedKey && seriesData.length > 0 ? (
        <>
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs font-semibold text-primary bg-primary-soft px-2.5 py-0.5 rounded-full">
              {availableSeries.find((opt) => opt.key === selectedKey)?.label}
            </span>
            <span className="text-xs text-muted-foreground">
              {seriesData.length} completed {seriesData.length === 1 ? "session" : "sessions"}
            </span>
          </div>

          <div className="mt-5 grid gap-6 lg:grid-cols-2">
            <Chart
              title="ROM Excursion (°)"
              data={seriesData}
              dataKey="rom"
              color="var(--chart-1)"
              legend="Range of Motion (°)"
              unit="°"
            />
            <Chart
              title="Performance Score (%)"
              data={seriesData}
              dataKey="score"
              color="var(--chart-2)"
              legend="Score (%)"
              unit="%"
            />
          </div>
        </>
      ) : (
        <div className="py-12 text-center text-xs text-muted-foreground leading-relaxed">
          No completed session data available for this patient.
          <br />
          Completed exercises performed in the Patient Portal will appear here.
        </div>
      )}
    </section>
  );
}

interface ChartProps {
  title: string;
  data: Array<{ name: string; rom: number; score: number; dateTime: string }>;
  dataKey: "rom" | "score";
  color: string;
  legend: string;
  unit: string;
}

function Chart({ title, data, dataKey, color, legend, unit }: ChartProps) {
  return (
    <div>
      <p className="text-xs font-semibold text-foreground uppercase tracking-wider">{title}</p>
      <div className="mt-3 h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="name"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            />
            <YAxis
              domain={["auto", "auto"]}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 10,
                border: "1px solid var(--border)",
                background: "var(--card)",
                fontSize: 12,
                color: "var(--foreground)",
              }}
              formatter={(val: any) => [`${val}${unit}`, legend]}
              labelFormatter={(_: any, payload: any[]) => {
                if (payload && payload[0]) {
                  return `${payload[0].payload.name} (${payload[0].payload.dateTime})`;
                }
                return "";
              }}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2.5}
              dot={{ r: 3.5, fill: color }}
              activeDot={{ r: 5 }}
              isAnimationActive={true}
              animationDuration={600}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 flex items-center justify-center gap-2 text-[11px] text-muted-foreground">
        <span className="inline-block h-0.5 w-4" style={{ background: color }} />
        {legend}
      </p>
    </div>
  );
}
