import { useMemo, useState } from "react";
import { Plus, Search } from "lucide-react";
import type { Patient } from "@/types/rehab";
import { cn } from "@/lib/utils";
import { StatusBadge } from "../../ui/StatusBadge";

interface PatientListProps {
  patients: Patient[];
  selectedId: string;
  onSelect: (id: string) => void;
  onAddNew: () => void;
}

export function PatientList({ patients, selectedId, onSelect, onAddNew }: PatientListProps) {
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
      <h2 className="text-lg font-bold text-foreground">Patients</h2>

      <div className="relative mt-4">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-primary" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search patient..."
          className="w-full rounded-xl border border-border bg-background py-2.5 pl-9 pr-3 text-sm text-foreground outline-none placeholder:text-muted-foreground focus:border-primary focus:ring-1 focus:ring-primary transition-all"
        />
      </div>

      <ul className="mt-4 space-y-2 max-h-[360px] overflow-y-auto pr-1">
        {filtered.map((patient, index) => {
          const isActive = patient.id === selectedId;
          return (
            <li
              key={patient.id}
              className="animate-fade-in-up"
              style={{
                animationDelay: `${index * 60}ms`,
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
                    {patient.name}
                  </span>
                </span>
                <span className="flex flex-col items-end gap-1">
                  <span className="text-sm font-semibold text-foreground">
                    {patient.recoveryScore}%
                  </span>
                  <StatusBadge value={patient.status} />
                </span>
              </button>
            </li>
          );
        })}
        {filtered.length === 0 ? (
          <li className="py-6 text-center text-sm text-muted-foreground">No patients found</li>
        ) : null}
      </ul>

      <button
        type="button"
        onClick={onAddNew}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-primary-soft py-3 text-sm font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground btn-interactive shadow-sm"
      >
        <Plus className="size-4" />
        Add New Patient
      </button>
    </section>
  );
}
