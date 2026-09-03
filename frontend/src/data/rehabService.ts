/**
 * Data access layer.
 */
import { patients as mockPatients, sessions as mockSessions } from "./mockData";
import type { DashboardStats, Patient, Session, PatientStatus } from "@/types/rehab";

export const API_BASE_URL = import.meta.env["VITE_API_BASE_URL"] || "http://127.0.0.1:8000";
export const DEMO_MODE = import.meta.env["VITE_DEMO_MODE"] === "true";

export function getWebSocketUrl(sessionId: string): string {
  const wsBase = API_BASE_URL.replace(/^http/, 'ws');
  return `${wsBase}/api/analysis/ws/${sessionId}`;
}

export async function fetchPatients(): Promise<Patient[]> {
  if (DEMO_MODE) return mockPatients;

  const response = await fetch(`${API_BASE_URL}/api/patients`);
  if (!response.ok) throw new Error("Failed to fetch patients");
  
  const data = await response.json();
  return data.patients.map((p: any) => ({
    id: p.patient_id,
    name: `Patient ${p.patient_id.replace(/\D/g, '') || p.patient_id}`,
    age: 45, // Backend doesn't store this yet
    gender: "Unknown", 
    condition: "Rehabilitation",
    startDate: p.last_active || new Date().toISOString(),
    sessionCount: p.total_sessions,
    recoveryScore: Math.min(100, p.total_sessions * 10 + 50), // Synthetic score for now
    status: (p.total_sessions > 3 ? "Good" : "Attention") as PatientStatus,
    avatarSeed: p.patient_id.toLowerCase(),
  }));
}

export async function fetchPatientSessions(
  patientId: string,
): Promise<(Session & { rawSessionId?: string; status?: string })[]> {
  if (DEMO_MODE) {
    return mockSessions.filter(s => s.patientId === patientId).map(s => ({
      ...s,
      rawSessionId: `mock-${s.id}`,
      status: "COMPLETED"
    }));
  }

  const response = await fetch(
    `${API_BASE_URL}/api/patients/${patientId}/sessions`,
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch sessions for ${patientId}`);
  }

  const data = await response.json();

  const mappedSessions = data.sessions.map(
    (
      session: {
        session_id: string;
        patient_id: string;
        exercise: string;
        started_at?: string;
        start_at?: string;
        status: string;
        results: any[];
      },
      index: number,
    ) => {
      const result = session.results && session.results.length > 0 ? session.results[0] : null;
      return {
        id: index + 1,
        rawSessionId: session.session_id,
        status: session.status,
        patientId: session.patient_id,
        dateTime: session.started_at || session.start_at || new Date().toISOString(),
        exercise: session.exercise
          .split("_")
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" "),
        repetitions: result ? result.repetitions : 0,
        rom: result && result.rom_max && result.rom_min ? result.rom_max - result.rom_min : 0,
        quality: (result && result.performance_score > 80 ? "Good" : "Fair") as any,
        score: result ? result.performance_score || 50 : 50,
      }
    }
  );
  
  // Sort sessions descending by dateTime
  return mappedSessions.sort((a: Session, b: Session) => new Date(b.dateTime).getTime() - new Date(a.dateTime).getTime());
}

export async function startSession(
  patientId: string,
  exercise: string = "elbow_flexion",
) {
  const response = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      patient_id: patientId,
      exercise: exercise,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error(`Error starting session (${response.status}):`, errorText);
    throw new Error(`Failed to start session: ${response.statusText}`);
  }

  return await response.json();
}

export async function endSession(sessionId: string) {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/end`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    const errorText = await response.text();
    console.error(
      `Error ending session ${sessionId} (${response.status}):`,
      errorText,
    );
    throw new Error(`Failed to end session: ${response.statusText}`);
  }

  return await response.json();
}

export function getPatients(): Patient[] {
  throw new Error("getPatients is deprecated. Use fetchPatients instead.");
}
export function getPatient(id: string): Patient | undefined {
  throw new Error("getPatient is deprecated. Use fetchPatients instead.");
}
export function getSessions(patientId: string): Session[] {
  throw new Error("getSessions is deprecated. Use fetchPatientSessions instead.");
}
export function getLatestSession(patientId: string): Session | undefined {
  throw new Error("getLatestSession is deprecated.");
}
export function getDashboardStats(): DashboardStats {
  throw new Error("getDashboardStats is deprecated.");
}
