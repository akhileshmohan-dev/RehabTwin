import { useMemo, useState } from "react";
import { Activity, Clock, Plus, Search, User, UserX } from "lucide-react";
import type { Patient } from "@/types/rehab";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/format";

interface PatientListProps {
  patients: Patient[];
  selectedId: string;
  onSelect: (id: string) => void;
  onAddPatientClick?: () => void;
}

export function PatientList({
  patients,
  selectedId,
  onSelect,
  onAddPatientClick,
}: PatientListProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        (p.name && p.name.toLowerCase().includes(q))
    );
  }, [patients, query]);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-foreground">Patients</h2>
          <span className="text-xs text-muted-foreground font-medium">
            {patients.length} Registered
          </span>
        </div>
        {onAddPatientClick && (
          <button
            type="button"
            onClick={onAddPatientClick}
            className="flex items-center gap-1.5 rounded-xl bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 transition-all btn-interactive"
          >
            <Plus className="size-3.5" />
            <span>Add Patient</span>
          </button>
        )}
      </div>

      <div className="relative mt-4">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or ID..."
          className="w-full rounded-xl border border-border bg-background py-2.5 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary transition-all"
        />
      </div>

      <ul className="mt-4 space-y-2.5 max-h-[500px] overflow-y-auto pr-1">
        {filtered.map((patient, index) => {
          const isActive = patient.id === selectedId;
          const hasActiveSession = (patient.activeSessions ?? 0) > 0;
          const isDeactivated = patient.status === "INACTIVE";

          return (
            <li
              key={patient.id}
              className="animate-fade-in-up"
              style={{
                animationDelay: `${index * 40}ms`,
                animationFillMode: "both",
              }}
            >
              <button
                type="button"
                onClick={() => onSelect(patient.id)}
                className={cn(
                  "flex w-full items-start gap-3 rounded-xl border p-3.5 text-left transition-all btn-interactive",
                  isActive
                    ? "border-primary bg-primary-soft shadow-sm"
                    : "border-border/60 hover:bg-muted/40 hover:border-border",
                  isDeactivated && "opacity-70 bg-muted/20"
                )}
              >
                <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-secondary text-xs font-bold text-secondary-foreground font-sans border border-border/40 mt-0.5">
                  {isDeactivated ? (
                    <UserX className="size-4 text-muted-foreground" />
                  ) : (
                    <User className="size-4 text-primary" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-foreground leading-tight truncate">
                      {patient.name || patient.id}
                    </span>
                    <span className="text-[10px] text-muted-foreground font-mono bg-muted/60 px-1.5 py-0.5 rounded">
                      {patient.id}
                    </span>
                    {isDeactivated ? (
                      <span className="inline-flex items-center rounded-full bg-destructive/10 px-2 py-0.2 text-[9px] font-semibold text-destructive border border-destructive/20">
                        Inactive
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.2 text-[9px] font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                        Active
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1.5 flex-wrap">
                    <span>
                      {patient.sessionCount ?? 0} {patient.sessionCount === 1 ? "session" : "sessions"}
                      {patient.completedSessions !== undefined && (
                        <span className="text-muted-foreground/70"> ({patient.completedSessions} completed)</span>
                      )}
                    </span>
                    {patient.lastActive && (
                      <span className="flex items-center gap-1 text-[11px] text-muted-foreground/80">
                        <Clock className="size-3" />
                        {formatDateTime(patient.lastActive)}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex flex-col items-end gap-1.5 shrink-0">
                  <span className="text-xs font-bold text-foreground">
                    {patient.avgPerformanceScore !== null && patient.avgPerformanceScore !== undefined
                      ? `${patient.avgPerformanceScore}%`
                      : "—"}
                  </span>
                  {hasActiveSession ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400 border border-amber-500/30">
                      <span className="size-1.5 rounded-full bg-amber-500 animate-pulse" />
                      In Session
                    </span>
                  ) : null}
                </div>
              </button>
            </li>
          );
        })}
        {filtered.length === 0 ? (
          <li className="py-8 text-center text-xs text-muted-foreground leading-relaxed">
            {patients.length === 0
              ? "No patients registered yet. Click 'Add Patient' to create one."
              : "No patients found matching your search."}
          </li>
        ) : null}
      </ul>
    </section>
  );
}
