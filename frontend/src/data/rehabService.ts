/**
 * Data access layer.
 * Every UI component reads data through these functions only, so the mock
 * source can later be swapped for FastAPI calls without touching the UI.
 */
import { patients, sessions } from "./mockData";
import type { DashboardStats, Patient, Session } from "@/types/rehab";

export const DATA_SOURCE = "Mock Data" as const;
export const DEMO_MODE = true;

export function getPatients(): Patient[] {
  return patients;
}

export function getPatient(id: string): Patient | undefined {
  return patients.find((p) => p.id === id);
}

export function getSessions(patientId: string): Session[] {
  return sessions
    .filter((s) => s.patientId === patientId)
    .sort((a, b) => a.id - b.id);
}

export function getLatestSession(patientId: string): Session | undefined {
  const list = getSessions(patientId);
  return list[list.length - 1];
}

export function getDashboardStats(): DashboardStats {
  const total = patients.length;
  const improving = patients.filter((p) => p.status !== "Attention").length;
  const needAttention = total - improving;
  const avg = Math.round(
    patients.reduce((sum, p) => sum + p.recoveryScore, 0) / total,
  );
  return {
    totalPatients: total,
    totalSessionsThisWeek: 24,
    improving,
    needAttention,
    avgRecoveryScore: avg,
  };
}
