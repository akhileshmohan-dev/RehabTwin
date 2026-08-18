import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  Excellent: "bg-success-soft text-success-foreground border border-success/10",
  Good: "bg-success-soft text-success-foreground border border-success/10",
  Fair: "bg-warning-soft text-warning-foreground border border-warning/10",
  Attention: "bg-warning-soft text-warning-foreground border border-warning/10",
  "Good Progress": "bg-success-soft text-success-foreground border border-success/10",
  "Excellent Progress": "bg-success-soft text-success-foreground border border-success/10",
  Poor: "bg-danger-soft text-destructive border border-destructive/10",
};

export function StatusBadge({ value, className }: { value: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-lg px-2 py-0.5 text-xs font-semibold leading-tight select-none",
        tones[value] ?? "bg-muted text-muted-foreground border border-border/40",
        className,
      )}
    >
      {value}
    </span>
  );
}
