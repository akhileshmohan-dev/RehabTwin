import { useState, useEffect, useCallback } from "react";
import {
  Activity,
  CalendarDays,
  CheckCircle2,
  Clock,
  IdCard,
  Edit3,
  UserX,
  UserCheck,
  Plus,
  Dumbbell,
  Sliders,
  AlertCircle,
  Phone,
  Mail,
  FileText,
  RotateCcw,
} from "lucide-react";
import type { Patient, PatientAssignment } from "@/types/rehab";
import { formatDateTime } from "@/lib/format";
import {
  fetchPatientAssignments,
  deactivateAssignment,
  updateAssignment,
  deactivatePatient,
  updatePatient,
} from "@/data/rehabService";
import { EditPatientModal } from "./EditPatientModal";
import { AssignExerciseModal } from "./AssignExerciseModal";
import { EditAssignmentModal } from "./EditAssignmentModal";

interface PatientDetailsProps {
  patient: Patient;
  onPatientUpdated?: () => void;
}

export function PatientDetails({ patient, onPatientUpdated }: PatientDetailsProps) {
  const [assignments, setAssignments] = useState<PatientAssignment[]>([]);
  const [loadingAssignments, setLoadingAssignments] = useState(false);
  const [assignmentError, setAssignmentError] = useState<string | null>(null);

  // Modals
  const [isEditPatientOpen, setIsEditPatientOpen] = useState(false);
  const [isAssignExerciseOpen, setIsAssignExerciseOpen] = useState(false);
  const [selectedAssignment, setSelectedAssignment] = useState<PatientAssignment | null>(null);
  const [isEditAssignmentOpen, setIsEditAssignmentOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const loadAssignments = useCallback(async () => {
    if (!patient.id) return;
    setLoadingAssignments(true);
    setAssignmentError(null);
    try {
      const data = await fetchPatientAssignments(patient.id);
      setAssignments(data);
    } catch (err: any) {
      console.error("Failed to fetch assignments:", err);
      setAssignmentError(err.message || "Could not load assignments.");
    } finally {
      setLoadingAssignments(false);
    }
  }, [patient.id]);

  useEffect(() => {
    loadAssignments();
  }, [loadAssignments]);

  const handleTogglePatientStatus = async () => {
    setActionLoading(true);
    try {
      if (patient.status === "INACTIVE") {
        await updatePatient(patient.id, { status: "ACTIVE" });
      } else {
        await deactivatePatient(patient.id);
      }
      onPatientUpdated?.();
    } catch (err: any) {
      alert(`Error updating patient status: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleAssignmentStatus = async (assign: PatientAssignment) => {
    try {
      if (assign.active) {
        await deactivateAssignment(patient.id, assign.id);
      } else {
        await updateAssignment(patient.id, assign.id, { active: true });
      }
      loadAssignments();
      onPatientUpdated?.();
    } catch (err: any) {
      alert(`Error updating assignment status: ${err.message}`);
    }
  };

  const hasActive = patient.activeSessions > 0;
  const isPatientInactive = patient.status === "INACTIVE";

  return (
    <div className="space-y-5">
      {/* Patient Profile Section */}
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-foreground">Patient Profile</h2>
            {isPatientInactive ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-destructive/15 px-2.5 py-0.5 text-xs font-semibold text-destructive border border-destructive/30">
                Inactive
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                Active
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {hasActive ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-600 dark:text-amber-400 border border-amber-500/30">
                <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
                Session Active
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                <CheckCircle2 className="size-3.5 text-muted-foreground" />
                Idle
              </span>
            )}

            <button
              type="button"
              onClick={() => setIsEditPatientOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted transition-colors shadow-xs"
            >
              <Edit3 className="size-3.5 text-muted-foreground" />
              Edit Patient
            </button>

            <button
              type="button"
              disabled={actionLoading}
              onClick={handleTogglePatientStatus}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors shadow-xs ${
                isPatientInactive
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20"
                  : "border-destructive/30 bg-destructive/10 text-destructive hover:bg-destructive/20"
              }`}
            >
              {isPatientInactive ? (
                <>
                  <UserCheck className="size-3.5" /> Reactivate
                </>
              ) : (
                <>
                  <UserX className="size-3.5" /> Deactivate
                </>
              )}
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-col sm:flex-row gap-5">
          <div className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-secondary text-base font-bold text-secondary-foreground font-sans border border-border/40 shadow-sm">
            {patient.id}
          </div>

          <div className="min-w-0 flex-1 space-y-3">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="text-xl font-bold text-foreground tracking-tight">{patient.name}</h3>
                {(patient.age || patient.gender) && (
                  <span className="text-xs text-muted-foreground font-medium bg-muted/40 px-2 py-0.5 rounded-md">
                    {[patient.age ? `${patient.age} yrs` : null, patient.gender].filter(Boolean).join(" • ")}
                  </span>
                )}
              </div>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5">
                <IdCard className="size-3.5" /> ID: {patient.id}
              </p>
            </div>

            {(patient.phone || patient.email) && (
              <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                {patient.phone && (
                  <span className="flex items-center gap-1">
                    <Phone className="size-3" /> {patient.phone}
                  </span>
                )}
                {patient.email && (
                  <span className="flex items-center gap-1">
                    <Mail className="size-3" /> {patient.email}
                  </span>
                )}
              </div>
            )}

            {patient.notes && (
              <div className="flex items-start gap-1.5 text-xs text-muted-foreground bg-muted/20 p-2.5 rounded-xl border border-border/40">
                <FileText className="size-3.5 shrink-0 mt-0.5 text-muted-foreground" />
                <span className="line-clamp-2">{patient.notes}</span>
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
              <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
                <p className="text-[11px] font-medium text-muted-foreground">Total Sessions</p>
                <p className="text-base font-bold text-foreground mt-0.5">{patient.sessionCount}</p>
              </div>
              <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
                <p className="text-[11px] font-medium text-muted-foreground">Active Sessions</p>
                <p className="text-base font-bold text-foreground mt-0.5">{patient.activeSessions}</p>
              </div>
              <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
                <p className="text-[11px] font-medium text-muted-foreground">Completed</p>
                <p className="text-base font-bold text-foreground mt-0.5">{patient.completedSessions}</p>
              </div>
              <div className="rounded-xl border border-border/60 bg-muted/30 p-2.5">
                <p className="text-[11px] font-medium text-muted-foreground">Avg. Score</p>
                <p className="text-base font-bold text-foreground mt-0.5">
                  {patient.avgPerformanceScore !== null ? `${patient.avgPerformanceScore}%` : "—"}
                </p>
              </div>
            </div>

            {patient.lastActive && (
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground pt-1">
                <Clock className="size-3.5" /> Last active: {formatDateTime(patient.lastActive)}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* Assigned Exercises Section */}
      <section className="rounded-2xl border border-border bg-card p-5 shadow-card card-interactive">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Dumbbell className="size-5 text-primary" />
            <h2 className="text-lg font-bold text-foreground">Assigned Rehabilitation Exercises</h2>
          </div>
          <button
            type="button"
            onClick={() => setIsAssignExerciseOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 transition-all btn-interactive"
          >
            <Plus className="size-3.5" />
            Assign Exercise
          </button>
        </div>

        {assignmentError && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            <span>{assignmentError}</span>
          </div>
        )}

        <div className="mt-4 space-y-3">
          {loadingAssignments ? (
            <div className="py-6 text-center text-xs text-muted-foreground animate-pulse">
              Loading exercise assignments...
            </div>
          ) : assignments.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border/80 p-6 text-center">
              <Dumbbell className="size-8 text-muted-foreground/40 mx-auto mb-2" />
              <p className="text-sm font-medium text-foreground">No exercises assigned yet</p>
              <p className="text-xs text-muted-foreground mt-1">
                Assign an exercise with target ROM and repetitions to enable patient training.
              </p>
              <button
                type="button"
                onClick={() => setIsAssignExerciseOpen(true)}
                className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20 px-3 py-1.5 text-xs font-semibold transition-colors"
              >
                <Plus className="size-3.5" /> Assign First Exercise
              </button>
            </div>
          ) : (
            assignments.map((assign) => (
              <div
                key={assign.id}
                className={`rounded-xl border p-4 transition-all ${
                  assign.active
                    ? "border-border bg-background/60 shadow-xs"
                    : "border-border/40 bg-muted/20 opacity-70"
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-sm text-foreground">
                        {assign.exercise_name || assign.exercise_id}
                      </span>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                          assign.side.toLowerCase() === "right"
                            ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                            : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                        }`}
                      >
                        {assign.side} Side
                      </span>
                      {assign.active ? (
                        <span className="inline-flex items-center rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                          Active Plan
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-muted/80 px-2 py-0.5 text-[10px] font-medium text-muted-foreground border border-border">
                          Inactive
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground pt-1">
                      <span>
                        <strong className="text-foreground font-semibold">Target ROM:</strong>{" "}
                        {assign.target_rom !== null ? `${assign.target_rom}°` : "Default"}
                      </span>
                      <span>•</span>
                      <span>
                        <strong className="text-foreground font-semibold">Target Reps:</strong>{" "}
                        {assign.target_repetitions !== null ? `${assign.target_repetitions}` : "Default"}
                      </span>
                      <span>•</span>
                      <span>
                        <strong className="text-foreground font-semibold">Frequency:</strong>{" "}
                        {assign.sessions_per_day}x / day
                      </span>
                    </div>

                    {assign.notes && (
                      <p className="text-xs text-muted-foreground/90 italic pt-1">
                        "{assign.notes}"
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedAssignment(assign);
                        setIsEditAssignmentOpen(true);
                      }}
                      className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted transition-colors"
                    >
                      <Sliders className="size-3 text-muted-foreground" />
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleToggleAssignmentStatus(assign)}
                      className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
                        assign.active
                          ? "border-destructive/30 bg-destructive/10 text-destructive hover:bg-destructive/20"
                          : "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20"
                      }`}
                    >
                      {assign.active ? (
                        <>Deactivate</>
                      ) : (
                        <>
                          <RotateCcw className="size-3" /> Reactivate
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </section>

      {/* Modals */}
      <EditPatientModal
        isOpen={isEditPatientOpen}
        patient={patient}
        onClose={() => setIsEditPatientOpen(false)}
        onPatientUpdated={() => {
          onPatientUpdated?.();
        }}
      />

      <AssignExerciseModal
        isOpen={isAssignExerciseOpen}
        patient={patient}
        onClose={() => setIsAssignExerciseOpen(false)}
        onAssigned={() => {
          loadAssignments();
          onPatientUpdated?.();
        }}
      />

      <EditAssignmentModal
        isOpen={isEditAssignmentOpen}
        assignment={selectedAssignment}
        onClose={() => {
          setIsEditAssignmentOpen(false);
          setSelectedAssignment(null);
        }}
        onUpdated={() => {
          loadAssignments();
          onPatientUpdated?.();
        }}
      />
    </div>
  );
}
