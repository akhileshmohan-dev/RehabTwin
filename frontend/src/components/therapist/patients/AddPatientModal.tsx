import React, { useState } from "react";
import { X } from "lucide-react";
import type { Patient } from "@/types/rehab";

interface AddPatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (patient: Patient) => void;
}

export function AddPatientModal({ isOpen, onClose, onAdd }: AddPatientModalProps) {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState<"Male" | "Female">("Male");
  const [condition, setCondition] = useState("");
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!name.trim() || !age.trim() || !condition.trim()) {
      setError("Please fill in all fields.");
      return;
    }

    const ageNum = parseInt(age, 10);
    if (isNaN(ageNum) || ageNum <= 0) {
      setError("Please enter a valid age.");
      return;
    }

    // Generate random mock ID
    const newId = `P00${Math.floor(Math.random() * 900) + 100}`;
    const newPatient: Patient = {
      id: newId,
      name: name.trim(),
      age: ageNum,
      gender,
      condition: condition.trim(),
      startDate: new Date().toISOString().split("T")[0],
      sessionCount: 0,
      recoveryScore: 0,
      status: "Attention",
      avatarSeed: newId.toLowerCase(),
    };

    onAdd(newPatient);
    onClose();

    // Reset Form
    setName("");
    setAge("");
    setGender("Male");
    setCondition("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-xs animate-backdrop-fade"
        onClick={onClose}
      />

      {/* Modal dialog box */}
      <div className="relative w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl animate-modal-scale-in z-10">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors btn-interactive"
        >
          <X className="size-5" />
        </button>

        <h3 className="text-xl font-bold text-foreground">Add New Patient</h3>
        <p className="text-sm text-muted-foreground mt-1">Register a patient to track their recovery path.</p>

        {error ? (
          <div className="mt-3 rounded-lg bg-destructive-foreground/10 border border-destructive/20 p-3 text-xs font-semibold text-destructive">
            {error}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-foreground uppercase tracking-wider">Patient Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. John Doe"
              className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-foreground outline-none focus:border-ring"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-foreground uppercase tracking-wider">Age</label>
              <input
                type="number"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                placeholder="Age"
                className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-foreground outline-none focus:border-ring"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-foreground uppercase tracking-wider">Gender</label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value as "Male" | "Female")}
                className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-foreground outline-none focus:border-ring"
              >
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-foreground uppercase tracking-wider">Condition</label>
            <input
              type="text"
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              placeholder="e.g. Rotator Cuff Tear"
              className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-sm text-foreground outline-none focus:border-ring"
            />
          </div>

          <div className="mt-6 flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-border bg-card px-4 py-2.5 text-sm font-semibold text-foreground hover:bg-muted transition-colors btn-interactive"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/95 transition-colors shadow-md btn-interactive"
            >
              Register Patient
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
