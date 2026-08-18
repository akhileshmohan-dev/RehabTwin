import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { AnimatedCounter } from "./AnimatedCounter";

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  sub: string;
  tone?: "primary" | "success" | "warning";
}

const tones = {
  primary: "bg-primary-soft text-primary",
  success: "bg-success-soft text-success-foreground",
  warning: "bg-warning-soft text-warning-foreground",
};

export function MetricCard({ icon: Icon, label, value, sub, tone = "primary" }: MetricCardProps) {
  // Parse out numeric values and suffixes (e.g. 72% -> 72, %) to enable counting animation
  const numericMatch = typeof value === "string" ? value.match(/^([\d.]+)(.*)$/) : null;
  const numValue = numericMatch ? parseFloat(numericMatch[1]) : parseFloat(value);
  const suffix = numericMatch ? numericMatch[2] : "";
  const isNumeric = !isNaN(numValue);

  return (
    <div className="flex items-center gap-4 rounded-2xl border border-border bg-card p-5 shadow-card card-interactive cursor-pointer">
      <div className={cn("flex size-11 shrink-0 items-center justify-center rounded-xl transition-transform duration-300 hover:rotate-6", tones[tone])}>
        <Icon className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-muted-foreground font-medium">{label}</p>
        <p className="text-2xl font-bold text-foreground tracking-tight mt-0.5">
          {isNumeric ? (
            <AnimatedCounter value={numValue} suffix={suffix} />
          ) : (
            value
          )}
        </p>
        <p className="truncate text-xs text-muted-foreground mt-0.5">{sub}</p>
      </div>
    </div>
  );
}
