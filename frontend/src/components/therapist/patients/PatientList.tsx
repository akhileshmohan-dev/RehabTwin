import { useMemo, useState } from "react";
import { Activity, Search } from "lucide-react";
import type { Patient } from "@/types/rehab";
import { cn } from "@/lib/utils";

interface PatientListProps {
  patients: Patient[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function PatientList({ patients, selectedId, onSelect }: PatientListProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) => p.id.toLowerCase().includes(q) || p.name.toLowerCase().includes(q),
    );
  }, [patients, query]);

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-foreground">Patients</h2>
        <span className="text-xs text-muted-foreground font-medium">
          {patients.length} Registered
        </span>
      </div>

      <div className="relative mt-4">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search patient..."
          className="w-full rounded-xl border border-border bg-background py-2.5 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary transition-all"
        />
      </div>

      <ul className="mt-4 space-y-2 max-h-[420px] overflow-y-auto pr-1">
        {filtered.map((patient, index) => {
          const isActive = patient.id === selectedId;
          const hasActiveSession = patient.activeSessions > 0;
          return (
            <li
              key={patient.id}
              className="animate-fade-in-up"
              style={{
                animationDelay: `${index * 50}ms`,
                animationFillMode: "both"
              }}
            >
              <button
                type="button"
                onClick={() => onSelect(patient.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-all btn-interactive",
                  isActive
                    ? "border-primary bg-primary-soft shadow-sm"
                    : "border-transparent hover:bg-muted/50",
                )}
              >
                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground font-sans">
                  {patient.id.slice(-3)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-foreground leading-tight">{patient.id}</span>
                  <span className="block truncate text-xs text-muted-foreground mt-0.5">
                    {patient.sessionCount} {patient.sessionCount === 1 ? "session" : "sessions"}
                  </span>
                </span>
                <span className="flex flex-col items-end gap-1">
                  <span className="text-xs font-semibold text-foreground">
                    {patient.avgPerformanceScore !== null ? `${patient.avgPerformanceScore}%` : "—"}
                  </span>
                  {hasActiveSession ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400 border border-amber-500/30">
                      <span className="size-1.5 rounded-full bg-amber-500 animate-pulse" />
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                      Idle
                    </span>
                  )}
                </span>
              </button>
            </li>
          );
        })}
        {filtered.length === 0 ? (
          <li className="py-8 text-center text-xs text-muted-foreground leading-relaxed">
            {patients.length === 0
              ? "No patients registered in the digital thread. Start a session in the Patient Portal."
              : "No patients found matching your search."}
          </li>
        ) : null}
      </ul>
    </section>
  );
}
