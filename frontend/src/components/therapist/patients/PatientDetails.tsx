import { CalendarDays, IdCard, User } from "lucide-react";
import type { Patient } from "@/types/rehab";
import { formatDate } from "@/lib/format";
import { StatusBadge } from "../../ui/StatusBadge";

export function PatientDetails({ patient }: { patient: Patient }) {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
      <h2 className="text-lg font-bold text-foreground">Patient Details</h2>

      <div className="mt-4 flex flex-col sm:flex-row gap-4">
        <div className="flex size-20 shrink-0 items-center justify-center rounded-2xl bg-secondary text-lg font-bold text-secondary-foreground font-sans border border-border/40 shadow-sm transition-transform hover:scale-105 duration-200">
          {patient.id}
        </div>
        <div className="min-w-0 space-y-2 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-xl font-bold text-foreground tracking-tight">{patient.name}</h3>
            <StatusBadge
              value={patient.status === "Attention" ? "Attention" : `${patient.status} Progress`}
            />
          </div>
          <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <IdCard className="size-4 text-muted-foreground/80" /> ID: {patient.id}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="size-4 text-muted-foreground/80" /> {patient.age} Years
            </span>
            <span className="inline-flex items-center gap-1.5">
              <User className="size-4 text-muted-foreground/80" /> {patient.gender}
            </span>
          </p>
          <div className="space-y-1 pt-1 text-sm">
            <p className="text-foreground">
              <span className="text-muted-foreground font-medium">Condition:</span> {patient.condition}
            </p>
            <p className="text-foreground flex flex-wrap gap-x-2">
              <span>
                <span className="text-muted-foreground font-medium">Start Date:</span>{" "}
                {formatDate(patient.startDate)}
              </span>
              <span className="text-muted-foreground/40">·</span>
              <span>
                <span className="text-muted-foreground font-medium">Sessions:</span> {patient.sessionCount}
              </span>
              <span className="text-muted-foreground/40">·</span>
              <span>
                <span className="text-muted-foreground font-medium">Recovery Score:</span>{" "}
                {patient.recoveryScore}%
              </span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
