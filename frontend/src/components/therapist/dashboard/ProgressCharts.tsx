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

export function ProgressCharts({ sessions }: { sessions: Session[] }) {
  const data = sessions.map((s) => ({
    name: `S${s.id}`,
    rom: s.rom,
    score: s.score,
  }));

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-foreground">Progress Trends</h2>
        <span className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground bg-muted/30">
          Last {data.length} Sessions
        </span>
      </div>

      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <Chart title="ROM Trend (°)" data={data} dataKey="rom" color="var(--chart-1)" legend="ROM (°)" />
        <Chart
          title="Performance Score (%)"
          data={data}
          dataKey="score"
          color="var(--chart-2)"
          legend="Score (%)"
        />
      </div>
    </section>
  );
}

interface ChartProps {
  title: string;
  data: Array<{ name: string; rom: number; score: number }>;
  dataKey: "rom" | "score";
  color: string;
  legend: string;
}

function Chart({ title, data, dataKey, color, legend }: ChartProps) {
  return (
    <div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <div className="mt-3 h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="name"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
            />
            <YAxis
              domain={["dataMin - 10", "dataMax + 10"]}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
            />
            <Tooltip
              contentStyle={{
                borderRadius: 12,
                border: "1px solid var(--border)",
                background: "var(--card)",
                fontSize: 12,
                color: "var(--foreground)",
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
              animationDuration={800}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 flex items-center justify-center gap-2 text-xs text-muted-foreground">
        <span className="inline-block h-0.5 w-5" style={{ background: color }} />
        {legend}
      </p>
    </div>
  );
}
