import { useState, useEffect } from "react";
import { X, Sliders, AlertCircle } from "lucide-react";
import { updateAssignment } from "@/data/rehabService";
import type { AssignmentUpdatePayload, PatientAssignment } from "@/types/rehab";

interface EditAssignmentModalProps {
  isOpen: boolean;
  assignment: PatientAssignment | null;
  onClose: () => void;
  onUpdated: () => void;
}

export function EditAssignmentModal({
  isOpen,
  assignment,
  onClose,
  onUpdated,
}: EditAssignmentModalProps) {
  const [formData, setFormData] = useState<AssignmentUpdatePayload>({
    target_rom: 140,
    target_repetitions: 10,
    sessions_per_day: 2,
    notes: "",
    active: true,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (assignment) {
      setFormData({
        target_rom: assignment.target_rom ?? undefined,
        target_repetitions: assignment.target_repetitions ?? undefined,
        sessions_per_day: assignment.sessions_per_day ?? 1,
        notes: assignment.notes || "",
        active: assignment.active,
      });
      setError(null);
    }
  }, [assignment]);

  if (!isOpen || !assignment) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await updateAssignment(assignment.patient_id, assignment.id, {
        target_rom: formData.target_rom ? Number(formData.target_rom) : undefined,
        target_repetitions: formData.target_repetitions ? Number(formData.target_repetitions) : undefined,
        sessions_per_day: formData.sessions_per_day ? Number(formData.sessions_per_day) : 1,
        notes: formData.notes?.trim() || "",
        active: formData.active,
      });
      onUpdated();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to update assignment.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-backdrop-fade">
      <div className="relative w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl animate-scale-up max-h-[90vh] overflow-y-auto">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          aria-label="Close"
        >
          <X className="size-5" />
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary-soft text-primary border border-primary/20">
            <Sliders className="size-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-foreground tracking-tight">Edit Exercise Assignment</h2>
            <p className="text-xs text-muted-foreground">
              {assignment.exercise_name} ({assignment.side}) for patient {assignment.patient_id}
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">Target ROM (°)</label>
              <input
                type="number"
                min="10"
                max="360"
                value={formData.target_rom ?? ""}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    target_rom: e.target.value ? parseFloat(e.target.value) : undefined,
                  })
                }
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">Target Reps</label>
              <input
                type="number"
                min="1"
                max="100"
                value={formData.target_repetitions ?? ""}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    target_repetitions: e.target.value ? parseInt(e.target.value, 10) : undefined,
                  })
                }
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-foreground mb-1">Sessions / Day</label>
              <input
                type="number"
                min="1"
                max="10"
                value={formData.sessions_per_day ?? 1}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    sessions_per_day: e.target.value ? parseInt(e.target.value, 10) : 1,
                  })
                }
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1">Status</label>
            <select
              value={formData.active ? "true" : "false"}
              onChange={(e) => setFormData({ ...formData, active: e.target.value === "true" })}
              className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
            >
              <option value="true">Active</option>
              <option value="false">Inactive / Suspended</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground mb-1">Therapist Notes / Instructions</label>
            <textarea
              rows={3}
              value={formData.notes || ""}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all resize-none"
            />
          </div>

          <div className="mt-6 flex items-center justify-end gap-3 pt-3 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90 transition-all disabled:opacity-50"
            >
              {isSubmitting ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
